# -*- coding: utf-8 -*-
"""
电机设置对话框
统一设置所有电机的减速比和方向
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QLineEdit,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QSpacerItem, QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont

from .motor_config_manager import motor_config_manager

class MotorSettingsDialog(QDialog):
    """电机设置对话框"""
    
    # 定义信号，当配置发生变化时发出
    config_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_manager = motor_config_manager
        self.init_ui()
        self.load_current_config()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("电机参数设置")
        self.setMinimumSize(650, 400)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("⚙️ 电机减速比与方向设置")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 说明信息
        info_label = QLabel(
            "💡 说明：\n"
            "• 减速比：电机转动圈数与输出端转动圈数的比值（如16:1表示电机转16圈，输出端转1圈）\n"
            "• 转向设置：该设置目标为设置机械臂关节方向与运动学一致，如果真实机械臂某关节转向与MuJoCo仿真相反，请设为'反向'\n"
            "• 配置将自动保存并应用到所有相关控件（具身智能、机械臂控制、手眼标定、示教器）"
        )
        info_label.setStyleSheet("""
            QLabel {
                background-color: #f0f8ff;
                border: 1px solid #b0d4f1;
                border-radius: 5px;
                padding: 10px;
                color: #2c3e50;
                font-size: 11px;
            }
        """)
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 设置表格
        self.create_settings_table(main_layout)
        
        # 按钮区域
        self.create_button_area(main_layout)
    
    def create_settings_table(self, parent_layout):
        """创建设置表格"""
        # 创建表格组
        table_group = QGroupBox("📊 电机参数配置表")
        table_layout = QVBoxLayout(table_group)
        
        # 创建表格
        self.settings_table = QTableWidget()
        self.settings_table.setRowCount(2)  # 2行：减速比和方向
        self.settings_table.setColumnCount(6)  # 6列：6个电机
        
        # 设置表头
        self.settings_table.setHorizontalHeaderLabels([f"电机{i+1}" for i in range(6)])
        self.settings_table.setVerticalHeaderLabels(["减速比", "转向"])
        
        # 表格样式设置
        self.settings_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.settings_table.verticalHeader().setDefaultSectionSize(80) 
        self.settings_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.settings_table.setSelectionMode(QTableWidget.NoSelection)
        self.settings_table.setAlternatingRowColors(True)
        self.settings_table.setMinimumHeight(150)
        
        # 初始化输入控件
        self.ratio_inputs = []
        self.direction_combos = []
        
        for i in range(6):
            # 减速比输入框（第一行）
            ratio_input = QLineEdit()
            ratio_input.setText("16.0")  # 默认值
            ratio_input.setAlignment(Qt.AlignCenter)
            ratio_input.setPlaceholderText("减速比")
            ratio_input.setStyleSheet("""
                QLineEdit {
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    padding: 5px;
                    font-size: 12px;
                }
                QLineEdit:focus {
                    border: 2px solid #4CAF50;
                }
            """)
            self.ratio_inputs.append(ratio_input)
            self.settings_table.setCellWidget(0, i, ratio_input)
            
            # 方向下拉框（第二行）
            direction_combo = QComboBox()
            direction_combo.addItem("正向", 1)
            direction_combo.addItem("反向", -1)
            direction_combo.setCurrentIndex(0)  # 默认正向
            direction_combo.setStyleSheet("""
                QComboBox {
                    border: 1px solid #ddd;
                    border-radius: 3px;
                    padding: 5px;
                    font-size: 12px;
                    background-color: white;
                }
                QComboBox:focus {
                    border: 2px solid #4CAF50;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: none;
                    border-left: 5px solid transparent;
                    border-right: 5px solid transparent;
                    border-top: 5px solid #888;
                    width: 0px;
                    height: 0px;
                }
            """)
            self.direction_combos.append(direction_combo)
            self.settings_table.setCellWidget(1, i, direction_combo)
        
        table_layout.addWidget(self.settings_table)
        parent_layout.addWidget(table_group)
    
    def create_button_area(self, parent_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置为默认")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #ef6c00;
            }
        """)
        reset_btn.clicked.connect(self.reset_to_default)
        button_layout.addWidget(reset_btn)
        
        # 添加弹性空间
        button_layout.addItem(QSpacerItem(40, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        
        # 取消按钮
        cancel_btn = QPushButton("取消")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # 确定按钮
        ok_btn = QPushButton("✅ 保存设置")
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 16px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
        """)
        ok_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(ok_btn)
        
        parent_layout.addLayout(button_layout)
    
    def load_current_config(self):
        """加载当前配置到界面"""
        try:
            # 加载减速比
            for i in range(6):
                motor_id = i + 1
                ratio = self.config_manager.get_motor_reducer_ratio(motor_id)
                self.ratio_inputs[i].setText(str(ratio))
                
                # 加载方向
                direction = self.config_manager.get_motor_direction(motor_id)
                # 设置下拉框：1=正向(索引0), -1=反向(索引1)
                self.direction_combos[i].setCurrentIndex(0 if direction == 1 else 1)
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载配置失败：{str(e)}")
    
    def save_settings(self):
        """保存设置"""
        try:
            # 验证并保存减速比
            for i in range(6):
                motor_id = i + 1
                
                # 验证减速比
                try:
                    ratio = float(self.ratio_inputs[i].text())
                    if ratio <= 0:
                        QMessageBox.warning(self, "输入错误", f"电机{motor_id}的减速比必须大于0")
                        return
                except ValueError:
                    QMessageBox.warning(self, "输入错误", f"电机{motor_id}的减速比输入无效，请输入数字")
                    return
                
                # 保存减速比
                self.config_manager.set_motor_reducer_ratio(motor_id, ratio)
                
                # 保存方向
                direction = self.direction_combos[i].currentData()
                self.config_manager.set_motor_direction(motor_id, direction)
            
            # 保存到文件
            if self.config_manager.save_config():
                # 发出配置变化信号
                self.config_changed.emit()
                
                # 显示成功信息
                ratios = [self.config_manager.get_motor_reducer_ratio(i+1) for i in range(6)]
                directions = ["正向" if self.config_manager.get_motor_direction(i+1) == 1 else "反向" for i in range(6)]
                
                info_text = "✅ 电机参数设置已保存并应用到所有相关控件！\n\n"
                info_text += "📊 当前配置：\n"
                for i in range(6):
                    info_text += f"电机{i+1}: {ratios[i]}:1, {directions[i]}\n"
                
                QMessageBox.information(self, "保存成功", info_text)
                self.accept()
            else:
                QMessageBox.critical(self, "保存失败", "无法保存配置文件，请检查文件权限")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存设置时发生错误：{str(e)}")
    
    def reset_to_default(self):
        """重置为默认设置"""
        reply = QMessageBox.question(
            self, 
            "确认重置", 
            "确定要重置为默认设置吗？\n\n默认设置：\n• 所有电机减速比：16.0:1\n• 所有电机方向：正向",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 重置配置管理器
                self.config_manager.reset_to_default()
                
                # 更新界面显示
                for i in range(6):
                    self.ratio_inputs[i].setText("16.0")
                    self.direction_combos[i].setCurrentIndex(0)  # 正向
                
                QMessageBox.information(self, "重置完成", "已重置为默认设置，请点击'保存设置'来应用更改")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"重置设置时发生错误：{str(e)}")
    
    def get_current_config(self):
        """获取当前界面的配置（用于预览）"""
        config = {
            "motor_reducer_ratios": {},
            "motor_directions": {}
        }
        
        try:
            for i in range(6):
                motor_id = i + 1
                ratio = float(self.ratio_inputs[i].text())
                direction = self.direction_combos[i].currentData()
                
                config["motor_reducer_ratios"][str(motor_id)] = ratio
                config["motor_directions"][str(motor_id)] = direction
                
        except Exception:
            pass  # 如果有错误，返回空配置
        
        return config 