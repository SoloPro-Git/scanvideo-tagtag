import os
from tqdm import tqdm

class VideoScanner:
    def __init__(self, config):
        self.config = config
        self.min_file_size = config['file_size'] * 1024 * 1024  # 转换为字节

    def scan_directory(self, directory, progress_callback=None):
        """扫描目录下的所有视频文件"""
        video_files = []
        total_files = sum([len(files) for _, _, files in os.walk(directory)])
        processed_files = 0

        # 视频文件扩展名
        video_extensions = ('.mp4', '.mkv', '.avi', '.wmv', '.mov', '.flv')

        for root, _, files in os.walk(directory):
            for file in files:
                processed_files += 1
                if progress_callback:
                    progress = int((processed_files / total_files) * 100)
                    progress_callback(progress)

                if file.lower().endswith(video_extensions):
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    
                    if file_size >= self.min_file_size:
                        video_files.append({
                            'name': file,
                            'path': file_path,
                            'size': file_size
                        })

        return video_files 