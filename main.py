import sys
import os
import io
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QFileDialog, QProgressBar, QLabel, QLineEdit,
                           QTextEdit, QFrame)
from PySide6.QtCore import QThread, Signal, Qt, QObject
from PySide6.QtGui import QFont, QIcon
import yaml
from scanner import VideoScanner
from processor import VideoProcessor

class StyledButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)

class StyledLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("""
            QLineEdit {
                padding: 5px;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
            }
        """)

class LogSignals(QObject):
    """用于发送日志信号的类"""
    log_signal = Signal(str)

class StreamToTextEdit:
    """将标准输出重定向到 QTextEdit"""
    def __init__(self, text_edit):
        self.text_edit = text_edit
        self.signals = LogSignals()
        self.signals.log_signal.connect(self.text_edit.append)
        self.buffer = []

    def write(self, text):
        if text.strip():  # 只处理非空文本
            self.signals.log_signal.emit(text.rstrip())

    def flush(self):
        pass

class WorkerThread(QThread):
    progress_updated = Signal(str, int)
    finished = Signal()
    error = Signal(str)
    log_updated = Signal(str)

    def __init__(self, scan_dir, output_path, log_output):
        super().__init__()
        self.scan_dir = scan_dir
        self.output_path = output_path
        self.log_output = log_output
        self.stdout_redirector = None

    def run(self):
        try:
            # 在工作线程中设置输出重定向
            self.stdout_redirector = StreamToTextEdit(self.log_output)
            old_stdout = sys.stdout
            sys.stdout = self.stdout_redirector

            # 加载配置
            with open('config.yaml', 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            # 创建扫描器和处理器
            scanner = VideoScanner(config)
            processor = VideoProcessor(config)

            # 扫描文件
            self.progress_updated.emit("正在扫描文件...", 0)
            self.log_updated.emit("开始扫描目录...")
            video_files = scanner.scan_directory(self.scan_dir, 
                                              progress_callback=lambda x: self.progress_updated.emit("扫描进度", x))
            self.log_updated.emit(f"找到 {len(video_files)} 个视频文件")

            # 处理文件
            self.progress_updated.emit("正在处理文件...", 0)
            self.log_updated.emit("开始处理文件...")
            results = processor.process_videos(video_files, 
                                           progress_callback=lambda x: self.progress_updated.emit("处理进度", x))

            # 导出结果
            self.log_updated.emit(f"正在导出结果到: {self.output_path}")
            processor.export_to_excel(results, self.output_path)
            self.finished.emit()

            # 恢复标准输出
            sys.stdout = old_stdout

        except Exception as e:
            self.error.emit(str(e))
            # 确保恢复标准输出
            sys.stdout = old_stdout

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('视频标签提取工具')
        self.setGeometry(100, 100, 800, 600)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
            }
            QLabel {
                color: #333333;
                font-size: 14px;
                font-weight: bold;
            }
            QProgressBar {
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)

        # 主窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 创建卡片式面板
        input_panel = self.create_panel("输入设置")
        progress_panel = self.create_panel("处理进度")
        log_panel = self.create_panel("运行日志")

        # 扫描目录部分
        scan_layout = QVBoxLayout()
        scan_header = QHBoxLayout()
        self.scan_dir_label = QLabel('扫描目录:')
        scan_header.addWidget(self.scan_dir_label)
        scan_layout.addLayout(scan_header)

        scan_input_layout = QHBoxLayout()
        self.scan_dir_input = StyledLineEdit()
        self.scan_dir_button = StyledButton('选择目录')
        self.scan_dir_button.setMaximumWidth(100)
        self.scan_dir_button.clicked.connect(self.select_scan_directory)
        scan_input_layout.addWidget(self.scan_dir_input)
        scan_input_layout.addWidget(self.scan_dir_button)
        scan_layout.addLayout(scan_input_layout)

        # 输出文件部分
        output_layout = QVBoxLayout()
        output_header = QHBoxLayout()
        self.output_label = QLabel('输出文件:')
        output_header.addWidget(self.output_label)
        output_layout.addLayout(output_header)

        output_input_layout = QHBoxLayout()
        self.output_input = StyledLineEdit()
        self.output_button = StyledButton('选择保存位置')
        self.output_button.setMaximumWidth(100)
        self.output_button.clicked.connect(self.select_output_file)
        output_input_layout.addWidget(self.output_input)
        output_input_layout.addWidget(self.output_button)
        output_layout.addLayout(output_input_layout)

        # 添加到输入面板
        input_panel_layout = input_panel.layout()
        input_panel_layout.addLayout(scan_layout)
        input_panel_layout.addLayout(output_layout)

        # 进度部分
        progress_layout = QVBoxLayout()
        self.progress_label = QLabel('准备就绪')
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                text-align: center;
                height: 25px;
            }
            QProgressBar::chunk {
                background-color: #2196F3;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_label)
        progress_layout.addWidget(self.progress_bar)

        # 开始按钮
        self.start_button = StyledButton('开始处理')
        self.start_button.clicked.connect(self.start_processing)
        progress_layout.addWidget(self.start_button)

        # 添加到进度面板
        progress_panel_layout = progress_panel.layout()
        progress_panel_layout.addLayout(progress_layout)

        # 日志输出区域
        log_layout = QVBoxLayout()
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setStyleSheet("""
            QTextEdit {
                background-color: white;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                padding: 5px;
                font-family: Consolas, Monaco, monospace;
                font-size: 13px;
            }
        """)
        log_layout.addWidget(self.log_output)

        # 添加到日志面板
        log_panel_layout = log_panel.layout()
        log_panel_layout.addLayout(log_layout)

        # 将所有面板添加到主布局
        main_layout.addWidget(input_panel)
        main_layout.addWidget(progress_panel)
        main_layout.addWidget(log_panel)

        central_widget.setLayout(main_layout)

    def create_panel(self, title):
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: white;
                border-radius: 8px;
                border: 1px solid #E0E0E0;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            QLabel {
                color: #1976D2;
                font-size: 16px;
                font-weight: bold;
            }
        """)
        layout.addWidget(title_label)
        
        panel.setLayout(layout)
        return panel

    def select_scan_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择扫描目录")
        if dir_path:
            self.scan_dir_input.setText(dir_path)
            self.log_output.append(f"已选择扫描目录: {dir_path}")

    def select_output_file(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "Excel Files (*.xlsx)")
        if file_path:
            if not file_path.endswith('.xlsx'):
                file_path += '.xlsx'
            self.output_input.setText(file_path)
            self.log_output.append(f"已选择输出文件: {file_path}")

    def start_processing(self):
        scan_dir = self.scan_dir_input.text()
        output_path = self.output_input.text()

        if not scan_dir or not output_path:
            self.log_output.append("错误: 请选择扫描目录和输出文件路径")
            return

        # 清空之前的日志
        self.log_output.clear()
        self.log_output.append("开始处理...")
        
        # 创建工作线程，传入日志输出控件
        self.worker = WorkerThread(scan_dir, output_path, self.log_output)
        self.worker.progress_updated.connect(self.update_progress)
        self.worker.finished.connect(self.process_finished)
        self.worker.error.connect(self.process_error)
        self.worker.log_updated.connect(self.update_log)

        self.start_button.setEnabled(False)
        self.worker.start()

    def update_progress(self, status, value):
        self.progress_label.setText(f'进度: {status}')
        self.progress_bar.setValue(value)

    def update_log(self, message):
        self.log_output.append(message)
        # 自动滚动到底部
        self.log_output.verticalScrollBar().setValue(
            self.log_output.verticalScrollBar().maximum()
        )

    def process_finished(self):
        self.progress_label.setText('处理完成!')
        self.start_button.setEnabled(True)
        self.log_output.append("处理完成!")

    def process_error(self, error_msg):
        self.progress_label.setText(f'错误: {error_msg}')
        self.start_button.setEnabled(True)
        self.log_output.append(f"错误: {error_msg}")

def main():
    # 创建应用程序实例
    app = QApplication(sys.argv)
    
    # 创建主窗口
    window = MainWindow()
    
    # 显示窗口
    window.show()
    
    # 启动事件循环
    return app.exec()

if __name__ == "__main__":
    # 使用 main() 函数并传递返回值给 sys.exit()
    sys.exit(main()) 