# -*- coding: utf-8 -*-
from PyQt5.QtWidgets import (
	QWidget, QGroupBox, QVBoxLayout, QHBoxLayout,
	QLabel, QComboBox, QLineEdit, QSpinBox, QPushButton,
	QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon
import sys
import os

# 添加项目根与core到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from core.control_claw import ClawController


class ClawConnectionWidget(QWidget):
	"""夹爪连接与控制界面"""
	
	# 定义信号：夹爪控制器状态变化时发射
	claw_controller_changed = pyqtSignal(object)  # 传递夹爪控制器实例（或None）
	
	def __init__(self):
		super().__init__()
		self.claw = None  
		self.init_ui()

	def init_ui(self):
		self.setWindowTitle("夹爪连接与控制")
		# 设置窗口图标
		icon_path = os.path.join(project_root, "logo.png")
		if os.path.exists(icon_path):
			self.setWindowIcon(QIcon(icon_path))
		
		main = QVBoxLayout(self)
		main.setContentsMargins(12, 12, 12, 12)
		main.setSpacing(12)

		# 连接参数
		conn_group = QGroupBox("连接参数")
		conn_layout = QHBoxLayout(conn_group)
		conn_layout.setSpacing(12)

		conn_layout.addWidget(QLabel("串口:"))
		self.port_edit = QLineEdit("COM1")
		self.port_edit.setFixedWidth(120)
		conn_layout.addWidget(self.port_edit)

		conn_layout.addWidget(QLabel("波特率:"))
		self.baud_spin = QSpinBox()
		self.baud_spin.setRange(1200, 2000000)
		self.baud_spin.setSingleStep(100)
		self.baud_spin.setValue(9600)
		self.baud_spin.setFixedWidth(120)
		conn_layout.addWidget(self.baud_spin)

		self.connect_btn = QPushButton("连接")
		self.connect_btn.setProperty("class", "success")
		self.connect_btn.clicked.connect(self.on_connect)
		conn_layout.addWidget(self.connect_btn)

		self.disconnect_btn = QPushButton("断开")
		self.disconnect_btn.setProperty("class", "danger")
		self.disconnect_btn.setEnabled(False)
		self.disconnect_btn.clicked.connect(self.on_disconnect)
		conn_layout.addWidget(self.disconnect_btn)

		conn_layout.addStretch()
		main.addWidget(conn_group)

		# 控制参数
		ctrl_group = QGroupBox("控制")
		ctrl_layout = QHBoxLayout(ctrl_group)
		ctrl_layout.setSpacing(12)

		ctrl_layout.addWidget(QLabel("闭合角度:"))
		self.close_spin = QSpinBox()
		self.close_spin.setRange(0, 90)
		self.close_spin.setValue(90)
		self.close_spin.setFixedWidth(100)
		self.close_spin.setToolTip("绝对角度（0–90°），示例：90=完全闭合")
		ctrl_layout.addWidget(self.close_spin)

		ctrl_layout.addWidget(QLabel("张开角度:"))
		self.open_spin = QSpinBox()
		self.open_spin.setRange(0, 90)
		self.open_spin.setValue(0)
		self.open_spin.setFixedWidth(100)
		self.open_spin.setToolTip("绝对角度（0–90°），示例：0=完全张开")
		ctrl_layout.addWidget(self.open_spin)

		self.open_btn = QPushButton("张开")
		self.open_btn.clicked.connect(self.on_open)
		self.open_btn.setEnabled(False)
		ctrl_layout.addWidget(self.open_btn)

		self.close_btn = QPushButton("闭合")
		self.close_btn.clicked.connect(self.on_close)
		self.close_btn.setEnabled(False)
		ctrl_layout.addWidget(self.close_btn)

		ctrl_layout.addStretch()
		main.addWidget(ctrl_group)

		# 绝对角度说明
		info = QLabel("角度为绝对位置：0°=完全张开，90°=完全闭合，范围 0–90°。")
		info.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-radius: 4px;")
		info.setWordWrap(True)
		main.addWidget(info)

	def on_connect(self):
		try:
			port = self.port_edit.text().strip()
			baud = int(self.baud_spin.value())
			if not port:
				QMessageBox.warning(self, "警告", "请输入有效串口")
				return
			self.claw = ClawController(port=port, baudrate=baud)
			self.claw.connect()
			self.connect_btn.setEnabled(False)
			self.disconnect_btn.setEnabled(True)
			self.open_btn.setEnabled(True)
			self.close_btn.setEnabled(True)
			
			# 设置夹爪控制器到全局状态管理器
			try:
				from core.embodied_core import embodied_func
				embodied_func._set_claw_controller(self.claw)
				print("✅ 夹爪控制器已设置到全局状态管理器")
			except Exception as e:
				print(f"⚠️ 设置夹爪控制器到全局状态失败: {e}")
			
			# 发射信号，传递夹爪控制器实例
			self.claw_controller_changed.emit(self.claw)
			
			QMessageBox.information(self, "成功", f"已连接夹爪：{port} @ {baud}")
		except Exception as e:
			self.claw = None
			# 发射信号，传递None表示连接失败
			self.claw_controller_changed.emit(None)
			QMessageBox.critical(self, "错误", f"连接失败：{e}")

	def on_disconnect(self):
		try:
			if self.claw:
				self.claw.disconnect()
			self.claw = None
			self.connect_btn.setEnabled(True)
			self.disconnect_btn.setEnabled(False)
			self.open_btn.setEnabled(False)
			self.close_btn.setEnabled(False)
			
			# 清除全局状态管理器中的夹爪控制器
			try:
				from core.embodied_core import embodied_func
				embodied_func._set_claw_controller(None)
				print("✅ 夹爪控制器已从全局状态管理器中清除")
			except Exception as e:
				print(f"⚠️ 清除夹爪控制器从全局状态失败: {e}")
			
			# 发射信号，传递None表示断开连接
			self.claw_controller_changed.emit(None)
			
			QMessageBox.information(self, "提示", "夹爪已断开")
		except Exception as e:
			# 即使断开时出错，也要发射信号更新状态
			self.claw = None
			
			# 清除全局状态管理器中的夹爪控制器（异常情况）
			try:
				from core.embodied_core import embodied_func
				embodied_func._set_claw_controller(None)
				print("✅ 夹爪控制器已从全局状态管理器中清除（异常情况）")
			except Exception as clear_error:
				print(f"⚠️ 清除夹爪控制器从全局状态失败（异常情况）: {clear_error}")
			
			self.claw_controller_changed.emit(None)
			QMessageBox.warning(self, "提醒", f"断开时出现问题：{e}")

	def on_open(self):
		if not self.claw or not self.claw.is_connected():
			QMessageBox.warning(self, "警告", "请先连接夹爪")
			return
		try:
			self.claw.open(self.open_spin.value())
		except Exception as e:
			QMessageBox.critical(self, "错误", f"张开失败：{e}")

	def on_close(self):
		if not self.claw or not self.claw.is_connected():
			QMessageBox.warning(self, "警告", "请先连接夹爪")
			return
		try:
			self.claw.close(self.close_spin.value())
		except Exception as e:
			QMessageBox.critical(self, "错误", f"闭合失败：{e}") 