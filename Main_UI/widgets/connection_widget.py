# -*- coding: utf-8 -*-
"""
电机连接控制组件
"""

import sys
import os
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox,
                             QLineEdit, QDialog, QDialogButtonBox, QFormLayout,
                             QMessageBox, QListWidget, QListWidgetItem,
                             QCheckBox, QProgressBar, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt5.QtGui import QFont

# 添加Control_SDK目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
control_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "Control_SDK")
sys.path.insert(0, control_sdk_dir)

from Control_SDK.Control_Core import ZDTMotorController

class ConnectionWidget(QWidget):
    """连接控制组件"""
    
    connection_changed = pyqtSignal(dict)  # 连接状态改变信号
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 存储电机实例 {motor_id: controller}
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)  # 增大边距
        layout.setSpacing(8)  # 增大间距
        
        # 创建连接状态组
        self.create_connection_group(layout)
        
        # 创建控制按钮组
        self.create_control_group(layout)
        
    def create_connection_group(self, parent_layout):
        """创建连接状态组"""
        group = QGroupBox("连接状态")
        layout = QHBoxLayout(group)
        layout.setSpacing(15)  # 增大间距
        
        # 状态标签
        self.status_label = QLabel("未连接")
        self.status_label.setProperty("class", "status-disconnected")
        layout.addWidget(QLabel("状态:"))
        layout.addWidget(self.status_label)
        
        # 连接信息标签
        self.info_label = QLabel("无连接信息")
        self.info_label.setStyleSheet("color: #6c757d; font-size: 12px;")  # 增大字体
        layout.addWidget(QLabel("连接信息:"))
        layout.addWidget(self.info_label)
        
        layout.addStretch()
        parent_layout.addWidget(group)
        
    def create_control_group(self, parent_layout):
        """创建控制按钮组"""
        group = QGroupBox("连接控制")
        layout = QHBoxLayout(group)
        layout.setSpacing(10)  # 增大按钮间距
        
        # 连接按钮
        self.connect_btn = QPushButton("连接电机")
        self.connect_btn.setProperty("class", "success")
        self.connect_btn.clicked.connect(self.show_connection_dialog)
        layout.addWidget(self.connect_btn)
        
        # 断开按钮
        self.disconnect_btn = QPushButton("断开连接")
        self.disconnect_btn.setProperty("class", "danger")
        self.disconnect_btn.clicked.connect(self.disconnect_all)
        self.disconnect_btn.setEnabled(False)
        layout.addWidget(self.disconnect_btn)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新状态")
        self.refresh_btn.clicked.connect(self.refresh_status)
        self.refresh_btn.setEnabled(False)
        layout.addWidget(self.refresh_btn)
        
        layout.addStretch()
        parent_layout.addWidget(group)
    
    def show_connection_dialog(self):
        """显示连接对话框"""
        dialog = ConnectionDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            connection_info = dialog.get_connection_info()
            self.connect_motors(connection_info)
    
    def connect_motors(self, connection_info):
        """连接电机"""
        try:
            # 先断开现有连接
            if self.motors:
                print("🔌 断开现有连接...")
                self.disconnect_all()
            
            port = connection_info['port']
            baudrate = connection_info['baudrate']
            motor_ids = connection_info['motor_ids']
            drive_version = connection_info.get('drive_version', 'Y')
            
            print(f"\n🔗 开始连接电机...")
            print(f"   串口: {port}")
            print(f"   波特率: {baudrate}")
            print(f"   目标电机ID: {motor_ids}")
            print(f"   驱动板版本: {drive_version}")
            
            # 禁用连接按钮，防止重复连接
            self.connect_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            total_motors = len(motor_ids)
            failed_motors = []
            success_motors = []
            
            # 连接每个电机
            for motor_id in motor_ids:
                try:
                    # 显示当前连接进度
                    self.status_label.setText(f"正在连接电机 {motor_id}...")
                    QApplication.processEvents()  # 更新界面
                    
                    motor = ZDTMotorController(
                        motor_id=motor_id,
                        interface_type="slcan",
                        shared_interface=True,
                        port=port,
                        baudrate=baudrate
                    )
                    
                    # 尝试连接
                    motor.connect()
                    
                    # 标记驱动板版本到实例（供UI使用）
                    setattr(motor, 'drive_version', drive_version)
                    
                    # 验证连接是否真的成功 - 尝试读取电机状态
                    try:
                        # 设置较短的超时时间来快速检测连接问题
                        motor.read_parameters.get_motor_status()
                        self.motors[motor_id] = motor
                        success_motors.append(motor_id)
                        print(f"✅ 电机 {motor_id} 连接并验证成功")
                        
                    except Exception as verify_error:
                        # 连接建立了但无法通信，断开连接
                        try:
                            motor.disconnect()
                        except:
                            pass
                        error_msg = f"连接建立但通信失败: {str(verify_error)}"
                        failed_motors.append((motor_id, error_msg))
                        print(f"❌ 电机 {motor_id} 通信验证失败: {error_msg}")
                    
                except Exception as e:
                    error_msg = str(e)
                    # 检查是否是超时错误
                    if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
                        error_msg = f"连接超时: {error_msg}"
                    failed_motors.append((motor_id, error_msg))
                    print(f"❌ 电机 {motor_id} 连接失败: {error_msg}")
                    continue
            
            # 更新连接状态
            self.update_connection_status()
            
            # 打印连接总结
            print(f"\n🔗 连接总结:")
            print(f"   目标电机: {total_motors} 个 {motor_ids}")
            print(f"   成功连接: {len(success_motors)} 个 {success_motors}")
            print(f"   连接失败: {len(failed_motors)} 个 {[motor_id for motor_id, _ in failed_motors]}")
            
            # 触发连接改变信号，附带版本
            try:
                payload = {mid: self.motors[mid] for mid in self.motors}
                # 为兼容可能的接收方结构，包装一个包含版本的字典
                self.connection_changed.emit(payload)
            except Exception:
                pass
            
            # 根据连接结果显示不同的消息
            if len(success_motors) == total_motors:
                # 全部连接成功
                QMessageBox.information(self, '连接成功', 
                                      f'✅ 成功连接所有 {total_motors} 个电机\n'
                                      f'电机ID: {success_motors}\n'
                                      f'驱动板版本: {drive_version}')
            elif len(success_motors) > 0:
                # 部分连接成功
                failed_ids = [motor_id for motor_id, _ in failed_motors]
                message = f'⚠️ 部分连接成功\n\n'
                message += f'成功连接: {len(success_motors)} 个电机 {success_motors}\n'
                message += f'连接失败: {len(failed_motors)} 个电机 {failed_ids}\n\n'
                message += f'驱动板版本: {drive_version}\n'
                message += '失败详情:\n'
                for motor_id, error in failed_motors:
                    message += f'电机{motor_id}: {error}\n'
                
                QMessageBox.warning(self, '部分连接成功', message)
            else:
                # 全部连接失败
                message = f'❌ 连接失败 - 没有成功连接任何电机\n\n'
                message += f'驱动板版本: {drive_version}\n\n'
                message += '失败详情:\n'
                for motor_id, error in failed_motors:
                    message += f'电机{motor_id}: {error}\n'
                
                QMessageBox.critical(self, '连接失败', message)
                
        except Exception as e:
            QMessageBox.critical(self, '连接错误', f'连接过程中发生错误:\n{str(e)}')
        finally:
            # 恢复按钮状态
            self.connect_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
    
    def disconnect_all(self, confirm: bool = True):
        """断开所有连接（可选确认）"""
        # 用户触发时弹出确认；程序内部（如关闭应用）可传 confirm=False 静默执行
        if confirm:
            reply = QMessageBox.question(
                self,
                '断开连接',
                '确定要断开所有电机连接吗？',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply != QMessageBox.Yes:
                return
        if not self.motors:
            return
            
        disconnected_motors = []
        failed_disconnections = []
        
        try:
            print(f"🔌 开始断开所有电机连接...")
            
            for motor_id, motor in self.motors.items():
                try:
                    motor.disconnect()
                    disconnected_motors.append(motor_id)
                    print(f"✅ 电机 {motor_id} 断开成功")
                except Exception as e:
                    failed_disconnections.append((motor_id, str(e)))
                    print(f"❌ 电机 {motor_id} 断开失败: {str(e)}")
            
            # 清理共享接口
            ZDTMotorController.close_all_shared_interfaces()
            print("🔗 共享接口已关闭")
            
            self.motors.clear()
            self.update_connection_status()
            
            # 显示断开结果
            if failed_disconnections:
                message = f"⚠️ 部分电机断开失败\n\n"
                message += f"成功断开: {len(disconnected_motors)} 个电机 {disconnected_motors}\n"
                message += f"断开失败: {len(failed_disconnections)} 个电机\n\n"
                message += "失败详情:\n"
                for motor_id, error in failed_disconnections:
                    message += f"电机{motor_id}: {error}\n"
                
            else:
                return
            
        except Exception as e:
            QMessageBox.warning(self, '断开连接', f'断开连接时发生错误:\n{str(e)}')
    
    def refresh_status(self):
        """刷新连接状态"""
        if not self.motors:
            return
            
        print(f"🔄 开始检查电机连接状态...")
        original_count = len(self.motors)
        
        # 检查每个电机的连接状态
        disconnected_motors = []
        connected_motors = []
        
        for motor_id, motor in list(self.motors.items()):
            try:
                # 尝试读取电机状态来检查连接
                motor.read_parameters.get_motor_status()
                connected_motors.append(motor_id)
                print(f"✅ 电机 {motor_id} 连接正常")
            except Exception as e:
                disconnected_motors.append(motor_id)
                print(f"❌ 电机 {motor_id} 连接断开: {str(e)}")
                # 移除断开连接的电机
                del self.motors[motor_id]
        
        # 更新连接状态
        self.update_connection_status()
        
        # 显示检查结果
        if disconnected_motors:
            current_count = len(self.motors)
            message = f"⚠️ 连接状态检查完成\n\n"
            message += f"原有连接: {original_count} 个电机\n"
            message += f"当前连接: {current_count} 个电机 {connected_motors}\n"
            message += f"断开连接: {len(disconnected_motors)} 个电机 {disconnected_motors}\n\n"
            message += "建议重新连接断开的电机"
            
            QMessageBox.warning(self, '连接状态检查', message)
        else:
            QMessageBox.information(self, '连接状态检查', 
                                  f'✅ 所有 {len(connected_motors)} 个电机连接正常\n'
                                  f'电机ID: {connected_motors}')
    
    def update_connection_status(self):
        """更新连接状态显示"""
        if self.motors:
            motor_ids = sorted(self.motors.keys())
            self.status_label.setText("已连接")
            self.status_label.setProperty("class", "status-connected")
            self.status_label.setStyle(self.status_label.style())  # 刷新样式
            self.info_label.setText(f"电机ID: {motor_ids}")
            
            self.connect_btn.setText("重新连接")
            self.disconnect_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
            
            # 发送连接改变信号
            self.connection_changed.emit(self.motors)
        else:
            self.status_label.setText("未连接")
            self.status_label.setProperty("class", "status-disconnected")
            self.status_label.setStyle(self.status_label.style())  # 刷新样式
            self.info_label.setText("无连接信息")
            
            self.connect_btn.setText("连接电机")
            self.disconnect_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            
            # 发送连接改变信号
            self.connection_changed.emit({})


class ConnectionDialog(QDialog):
    """连接配置对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("电机连接配置")
        self.setModal(True)
        self.resize(450, 450)  # 增大对话框尺寸以适应新内容
        
        # 设置窗口图标
        try:
            from PyQt5.QtGui import QIcon
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        
        self.init_ui()
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        
        # 创建表单
        form_layout = QFormLayout()
        
        # 串口设置
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(['COM1', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5'])
        form_layout.addRow("串口:", self.port_combo)
        
        # 波特率设置
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(['500000', '250000', '125000', '1000000'])
        self.baudrate_combo.setCurrentText('500000')
        form_layout.addRow("波特率:", self.baudrate_combo)
        
        # 新增：驱动板版本选择（影响回零模式）
        self.drive_version_combo = QComboBox()
        self.drive_version_combo.addItems(['Y', 'X'])  # Y版支持“回到坐标原点/掉电位置”，X版不支持
        self.drive_version_combo.setCurrentText('Y')
        form_layout.addRow("驱动板版本:", self.drive_version_combo)
        
        layout.addLayout(form_layout)
        
        # 添加连接注意事项
        tips_group = QGroupBox("💡 连接注意事项")
        tips_layout = QVBoxLayout(tips_group)
        
        tips_text = QLabel(
            "• 确保CAN转USB设备已正确连接\n"
            "• 检查电机电源是否开启\n" 
            "• 确认电机ID设置正确（通过DIP开关或软件配置）\n"
            "• 波特率设置需与电机控制器匹配\n"
            "• 连接失败时，检查串口是否被其他程序占用\n"
            "• 系统会验证每个电机的通信状态，确保连接质量"
        )
        tips_text.setWordWrap(True)
        tips_text.setStyleSheet("color: #666; font-size: 10px;")
        tips_layout.addWidget(tips_text)
        
        layout.addWidget(tips_group)
        
        # 电机ID设置
        id_group = QGroupBox("电机ID设置")
        id_layout = QVBoxLayout(id_group)
        
        # 快速设置
        quick_layout = QHBoxLayout()
        quick_layout.addWidget(QLabel("快速设置:"))
        
        self.single_btn = QPushButton("单电机(ID=1)")
        self.single_btn.clicked.connect(lambda: self.set_motor_ids([1]))
        quick_layout.addWidget(self.single_btn)
        
        self.dual_btn = QPushButton("双电机(ID=1,2)")
        self.dual_btn.clicked.connect(lambda: self.set_motor_ids([1, 2]))
        quick_layout.addWidget(self.dual_btn)
        
        self.triple_btn = QPushButton("机械臂")
        self.triple_btn.clicked.connect(lambda: self.set_motor_ids([1, 2, 3, 4, 5, 6]))
        quick_layout.addWidget(self.triple_btn)
        
        quick_layout.addStretch()
        id_layout.addLayout(quick_layout)
        
        # 自定义设置
        custom_layout = QHBoxLayout()
        custom_layout.addWidget(QLabel("自定义ID:"))
        
        self.motor_ids_edit = QLineEdit()
        self.motor_ids_edit.setPlaceholderText("例如: 1,2,3,4,5,6")
        self.motor_ids_edit.setText("1")
        custom_layout.addWidget(self.motor_ids_edit)
        
        id_layout.addLayout(custom_layout)
        layout.addWidget(id_group)
        
        # 按钮
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def set_motor_ids(self, motor_ids):
        """设置电机ID"""
        self.motor_ids_edit.setText(','.join(map(str, motor_ids)))
    
    def get_connection_info(self):
        """获取连接信息"""
        try:
            motor_ids_text = self.motor_ids_edit.text().strip()
            motor_ids = [int(x.strip()) for x in motor_ids_text.split(',') if x.strip()]
            
            return {
                'port': self.port_combo.currentText(),
                'baudrate': int(self.baudrate_combo.currentText()),
                'motor_ids': motor_ids,
                'drive_version': self.drive_version_combo.currentText()
            }
        except ValueError as e:
            QMessageBox.warning(self, '参数错误', '电机ID格式错误，请输入数字，用逗号分隔')
            return None 