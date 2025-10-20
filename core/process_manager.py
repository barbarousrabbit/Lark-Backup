"""
Process Manager Module
控制程序单例运行，新实例会替换旧实例
"""

import os
import sys
import time
import signal
import logging
import psutil
import atexit
import subprocess

class SingleInstanceManager:
    """管理程序单例，新实例会优雅终止旧实例"""
    
    def __init__(self, pid_file_name="LarkBackup.pid"):
        """初始化单例管理器"""
        self.app_dir = self._get_application_path()
        self.pid_file = os.path.join(self.app_dir, pid_file_name)
        self.is_running = False
        
        logging.info(f"📝 PID file location: {self.pid_file}")
        
        # 获取自己的PID以供后续比较
        self.own_pid = os.getpid()
        logging.info(f"🆔 Current process ID: {self.own_pid}")
        
        # 清理过期PID文件
        self._cleanup_stale_pid_file()
        
        # 注册退出清理函数
        atexit.register(self.cleanup)
    
    def _get_application_path(self):
        """获取应用程序路径"""
        if getattr(sys, 'frozen', False):
            return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(sys.argv[0]))
    
    def start(self):
        """启动新实例，如有旧实例则终止它"""
        # 1. 读取现有PID文件
        old_pid = self._read_pid_file()
        
        # 2. 如果找到旧PID，尝试终止对应的进程
        if old_pid:
            if old_pid == self.own_pid:
                logging.info(f"ℹ️ PID file contains the same PID as the current process, no termination needed")
            else:
                logging.info(f"🔄 Found old PID: {old_pid}, terminating...")
                self._terminate_process_by_pid(old_pid)
                # 短暂等待旧进程结束
                time.sleep(0.5)
        
        # 3. 无论如何，尝试终止所有同名Python进程(排除自己)
        self._kill_same_script_processes()
        
        # 4. 写入自己的PID
        self._write_pid_file()
        self.is_running = True
        logging.info(f"✅ New instance, PID: {self.own_pid})")
        return True
    
    def _cleanup_stale_pid_file(self):
        """清理过期的PID文件"""
        if not os.path.exists(self.pid_file):
            return
            
        try:
            # 读取PID文件
            with open(self.pid_file, 'r') as f:
                content = f.read().strip()
            
            try:
                pid = int(content)
                # 检查PID是否存在且不是自己
                if pid != self.own_pid:
                    # 检查进程是否存在
                    if not psutil.pid_exists(pid):
                        logging.info(f"🧹 Cleaned expired PID {pid} not exists")
                        os.remove(self.pid_file)
            except ValueError:
                # PID文件内容无效
                logging.warning(f"⚠️ PID file content is invalid: {content}, deleting it")
                os.remove(self.pid_file)
        except Exception as e:
            logging.error(f"❌ Error checking PID file: {str(e)}")
    
    def _read_pid_file(self):
        """读取PID文件，返回存储的PID或None"""
        if not os.path.exists(self.pid_file):
            return None
            
        try:
            with open(self.pid_file, 'r') as f:
                pid = int(f.read().strip())
                return pid if pid > 0 else None
        except (IOError, ValueError) as e:
            logging.error(f"❌ Error reading PID file: {str(e)}")
            # 如果文件存在但内容无效，尝试删除它
            try:
                os.remove(self.pid_file)
                logging.info(f"🧹 Deleted invalid PID file")
            except:
                pass
            return None
    
    def _write_pid_file(self):
        """写入当前进程PIDto file"""
        try:
            # 确保PID文件目录存在
            pid_dir = os.path.dirname(self.pid_file)
            if pid_dir and not os.path.exists(pid_dir):
                os.makedirs(pid_dir)
                
            with open(self.pid_file, 'w') as f:
                f.write(str(self.own_pid))
                
            logging.info(f"✍️ Written PID {self.own_pid} to file")
        except IOError as e:
            logging.error(f"❌ Error writing PID file: {str(e)}")
    
    def _terminate_process_by_pid(self, pid):
        """终止指定PID的进程"""
        try:
            # 确保不会终止自己
            if pid == self.own_pid:
                logging.warning(f"⚠️ Attempted to terminate own process, skipping")
                return False
                
            # 检查进程是否存在
            if not psutil.pid_exists(pid):
                logging.info(f"ℹ️ PID {pid} not exists, no termination needed")
                return True
                
            # 1. 首先尝试通过psutil终止
            try:
                process = psutil.Process(pid)
                process_name = process.name()
                
                # 终止进程
                process.terminate()
                logging.info(f"🔄 Sent termination signal {process_name} (PID: {pid})")
                
                # 等待进程终止
                start_time = time.time()
                while psutil.pid_exists(pid) and time.time() - start_time < 2:
                    time.sleep(0.1)
                
                # 如果进程仍然存在，强制终止
                if psutil.pid_exists(pid):
                    process.kill()
                    logging.info(f"🔄 Forced termination of process (PID: {pid})")
                    time.sleep(0.1)
                
                if not psutil.pid_exists(pid):
                    logging.info(f"✅ Terminated PID: {pid})")
                    return True
            except psutil.NoSuchProcess:
                return True
            except psutil.AccessDenied:
                logging.warning(f"⚠️ Could not access process (PID: {pid}), trying other methods")
            except Exception as e:
                logging.error(f"❌ Error terminating process: {str(e)}")
            
            # 2. 如果psutil方法失败，尝试使用操作系统命令
            if sys.platform.startswith('win'):
                try:
                    subprocess.run(['taskkill', '/F', '/PID', str(pid)], 
                                   stdout=subprocess.DEVNULL, 
                                   stderr=subprocess.DEVNULL)
                    logging.info(f"✅ Process terminated via taskkill (PID: {pid})")
                    return True
                except Exception as e:
                    logging.error(f"❌ taskkill termination failed: {str(e)}")
            else:
                # Unix系统
                try:
                    os.kill(pid, signal.SIGKILL)
                    logging.info(f"✅ Process terminated via kill signal (PID: {pid})")
                    return True
                except Exception as e:
                    logging.error(f"❌ kill termination failed: {str(e)}")
                    
            return False
        except Exception as e:
            logging.error(f"❌ Error during process termination: {str(e)}")
            return False
    
    def _kill_same_script_processes(self):
        """终止所有运行相同脚本的其他Python进程（优化版：更精确的进程识别）"""
        try:
            # 确定当前程序的特征
            if getattr(sys, 'frozen', False):
                # PyInstaller打包的可执行文件
                current_exe = os.path.abspath(sys.executable).lower()
                current_script_name = os.path.basename(current_exe)
                identification_method = "executable_path"
            else:
                # Python脚本
                current_exe = None
                current_script = os.path.abspath(sys.argv[0]).lower()
                current_script_name = os.path.basename(current_script)
                identification_method = "script_path"
            
            logging.info(f"🔍 Looking for processes to terminate using {identification_method}")
            logging.info(f"🎯 Target identifier: {current_script_name}")
            
            # 计数器
            terminated_count = 0
            checked_count = 0
            
            # 获取当前进程和其子进程的ID列表，避免终止自己的子进程
            own_process_ids = set()
            try:
                own_process = psutil.Process(self.own_pid)
                own_process_ids.add(self.own_pid)
                
                # 添加当前进程的所有子进程
                for child in own_process.children(recursive=True):
                    try:
                        own_process_ids.add(child.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                logging.debug(f"Protected process IDs: {own_process_ids}")
            except Exception as e:
                logging.error(f"❌ Error getting process info: {str(e)}")
            
            # 遍历所有进程
            for proc in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
                try:
                    # 跳过自己及其子进程
                    if proc.pid in own_process_ids:
                        continue
                    
                    checked_count += 1
                    is_target = False
                    target_reason = ""
                    
                    if current_exe:
                        # 对于打包的可执行文件，进行更精确的匹配
                        try:
                            proc_exe = proc.exe()
                            if proc_exe:
                                proc_exe_lower = proc_exe.lower()
                                # 必须是完全相同的可执行文件路径
                                if proc_exe_lower == current_exe:
                                    is_target = True
                                    target_reason = f"same executable: {proc_exe}"
                                # 或者至少文件名相同且在相同目录
                                elif (os.path.basename(proc_exe_lower) == current_script_name and 
                                      os.path.dirname(proc_exe_lower) == os.path.dirname(current_exe)):
                                    is_target = True
                                    target_reason = f"same name and directory: {proc_exe}"
                        except (psutil.AccessDenied, psutil.ZombieProcess, FileNotFoundError):
                            pass
                    else:
                        # 对于Python脚本，进行更精确的匹配
                        try:
                            cmdline = proc.cmdline()
                            if len(cmdline) >= 2:
                                # 检查是否是Python进程
                                if 'python' in cmdline[0].lower():
                                    # 遍历命令行参数，寻找脚本路径
                                    for arg in cmdline[1:]:  # 跳过python.exe
                                        arg_lower = arg.lower()
                                        # 必须是完全相同的脚本路径
                                        if arg_lower == current_script:
                                            is_target = True
                                            target_reason = f"same script path: {arg}"
                                            break
                                        # 或者脚本名称相同且包含关键标识符
                                        elif (os.path.basename(arg_lower) == current_script_name and 
                                              'lark' in arg_lower and 'backup' in arg_lower):
                                            is_target = True
                                            target_reason = f"same script name with LarkBackup identifier: {arg}"
                                            break
                        except (psutil.AccessDenied, psutil.ZombieProcess):
                            pass
                    
                    # 如果是目标进程，终止它
                    if is_target:
                        proc_info = f"{proc.name()} (PID: {proc.pid})"
                        logging.info(f"🎯 Found target process: {proc_info}")
                        logging.info(f"📝 Match reason: {target_reason}")
                        
                        # 添加最后的安全检查：确认不是重要系统进程
                        proc_name = proc.name().lower()
                        if any(sys_proc in proc_name for sys_proc in ['system', 'winlogon', 'csrss', 'smss', 'services']):
                            logging.warning(f"⚠️ Safety check: Skipping system process {proc_info}")
                            continue
                        
                        # 尝试获取并终止子进程
                        try:
                            child_processes = proc.children(recursive=True)
                            for child in child_processes:
                                try:
                                    child_info = f"{child.name()} (PID: {child.pid})"
                                    logging.info(f"🔄 Terminating child process: {child_info}")
                                    self._terminate_process_by_pid(child.pid)
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    continue
                        except Exception as e:
                            logging.warning(f"⚠️ Error getting child processes: {str(e)}")
                        
                        # 终止主进程
                        if self._terminate_process_by_pid(proc.pid):
                            terminated_count += 1
                            logging.info(f"✅ Successfully terminated: {proc_info}")
                        else:
                            logging.warning(f"⚠️ Failed to terminate: {proc_info}")
                
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
                except Exception as e:
                    logging.error(f"❌ Error processing process: {str(e)}")
            
            # 记录详细的终止结果
            logging.info(f"📊 Process termination summary:")
            logging.info(f"   - Checked {checked_count} processes")
            logging.info(f"   - Terminated {terminated_count} target processes")
            logging.info(f"   - Protected {len(own_process_ids)} own processes")
            
            if terminated_count > 0:
                logging.info(f"✅ Successfully terminated {terminated_count} same program processes")
                return True
            else:
                logging.info(f"ℹ️ No other same program processes found to terminate")
                return False
                
        except Exception as e:
            logging.error(f"❌ Error terminating same program processes: {str(e)}")
            return False
    
    def cleanup(self):
        """清理PID文件和子进程"""
        if self.is_running and os.path.exists(self.pid_file):
            try:
                # 读取PID文件确认是否是当前进程
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                    
                # 只有当PID文件中的PID与当前进程相同时才删除
                if pid == self.own_pid:
                    # 清理所有子进程
                    try:
                        process = psutil.Process(self.own_pid)
                        children = process.children(recursive=True)
                        for child in children:
                            try:
                                child_info = f"{child.name()} (PID: {child.pid})"
                                logging.info(f"🧹 Cleaning up child process: {child_info}")
                                child.terminate()
                                # 给子进程一点时间来终止
                                child.wait(timeout=1)
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                                # 如果子进程已经not exists或无法访问，或者超时，尝试强制终止
                                try:
                                    child.kill()
                                except:
                                    pass
                    except Exception as e:
                        logging.error(f"❌ Error cleaning up child processes: {str(e)}")
                    
                    # 删除PID文件
                    os.remove(self.pid_file)
                    logging.info(f"✅ Deleted PID file")
                else:
                    logging.info(f"ℹ️ PID file points to another process ({pid}), skipping deletion")
            except Exception as e:
                logging.error(f"❌ Error deleting PID file: {str(e)}")
                
        # 强制刷新所有日志
        try:
            logging.info(f"🧹 Performing final cleanup to ensure all logs are written")
            for handler in logging.root.handlers:
                try:
                    handler.flush()
                except:
                    pass
        except:
            pass

def init_single_instance_manager(pid_file="LarkBackup.pid"):
    """初始化并返回单例管理器"""
    return SingleInstanceManager(pid_file_name=pid_file) 