import time
import requests
import pandas as pd
from openai import OpenAI
from tqdm import tqdm

class VideoProcessor:
    def __init__(self, config):
        self.config = config
        # 简化 OpenAI 客户端初始化
        self.openai_client = OpenAI(
            api_key=config['openai']['api_key'],
            base_url=config['openai']['api_endpoint']
        )
        
        # 初始化请求会话，复用连接
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive'
        })
        
    def extract_code(self, filename):
        """使用LLM从文件名中提取番号"""
        try:
            time.sleep(self.config['llm']['delay'])
            
            prompt = f"""请从以下文件名中提取番号。只需要返回番号，不需要其他内容。
            番号命名规则相对复杂，不同片商可能会有所差异，但通常包含以下几种元素：
            片商代码： 由 2-3 个英文字母组成，代表特定的 AV 片商，例如：
            IPX：IDEAPOCKET
            MIDE：MOODYZ
            JUFD：ジュマンジ（JUMANJI）
            SNIS：SOD(Soft On Demand)
            女优代码： 部分番号会包含女优的专属代码，通常为 1-2 个英文字母或数字。
            日期代码： 有些番号会包含影片拍摄或发行日期，格式可能为年月日或年月。
            系列代码： 若影片属于某个系列，番号中会包含该系列的代码。
            作品序号： 每部影片都有一个独特的序号，通常为 3-4 位数字。
            以下是一些可能出现的番号示例，仅供参考：
            IPX-123
            MIDE-456
            JUFD-789
            SNIS-001
            ABW-002
            PPPD-003
            HEYZO-004
            DBA-005
            RKI-006
            CESD-007
            DASD-008
            IPVR-009
            SVR-010
            STARS-011
            SIRO-012
            PRESTIGE-013
            ATTACKGIRL-014
            E-BODY-015
            Kawaii-016
            MAXING-017
            cawd-441
            如果找不到番号，请返回空字符串。
            文件名: {filename}"""
            
            completion = self.openai_client.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[
                    {"role": "system", "content": "你是一个专门提取视频番号的助手。你的任务是从文件名中提取番号，只返回番号本身，不需要其他内容。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config['llm']['max_tokens'],
                temperature=self.config['llm']['temperature']
            )
            
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"提取番号时出错: {str(e)}")
            return ""

    def fetch_tags(self, code):
        """从网页获取标签"""
        if not code:
            return []
            
        try:
            time.sleep(self.config['request']['delay'])
            
            url = f"https://www.javbus.com/{code}"
            
            response = self.session.get(
                url, 
                timeout=self.config['request']['timeout']
            )
            response.raise_for_status()
            
            # 使用LLM提取标签
            time.sleep(self.config['llm']['delay'])
            
            prompt = f"""请从以下网页内容中提取影片的所有标签，用逗号分隔。
            只需要返回影片的标签列表，不需要其他内容。
            网页内容: {response.text}"""
            
            completion = self.openai_client.chat.completions.create(
                model=self.config['openai']['model'],
                messages=[
                    {"role": "system", "content": "你是一个专门提取视频标签的助手。你的任务是从网页内容中提取所有相关标签，用逗号分隔返回。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.config['llm']['max_tokens'],
                temperature=self.config['llm']['temperature']
            )
            
            tags = completion.choices[0].message.content.strip()
            return [tag.strip() for tag in tags.split(',') if tag.strip()]
            
        except Exception as e:
            print(f"获取标签时出错: {str(e)}")
            return []

    def process_videos(self, video_files, progress_callback=None):
        """处理视频文件列表，带整体重试机制"""
        results = []
        total = len(video_files)
        
        for i, video in enumerate(video_files):
            if progress_callback:
                progress = int((i / total) * 100)
                progress_callback(progress)
            
            # 获取重试次数
            max_retries = self.config['llm'].get('process_retries', 3)
            retry_count = 0
            
            while retry_count < max_retries:
                try:
                    # 提取番号
                    code = self.extract_code(video['name'])
                    print(f"处理文件: {video['name']}")
                    print(f"提取的番号: {code}")
                    
                    # 获取标签
                    tags = self.fetch_tags(code)
                    print(f"获取的标签: {tags}\n")
                    
                    # 如果标签为空，视为失败，触发重试
                    if not tags:
                        retry_count += 1
                        print(f"标签获取失败，重试 {retry_count}/{max_retries}")
                        time.sleep(self.config['llm']['delay'] * 2)
                        continue
                    
                    # 成功获取标签，添加到结果
                    results.append({
                        'name': video['name'],
                        'path': video['path'],
                        'code': code,
                        'tags': ', '.join(tags)
                    })
                    break  # 成功处理，跳出重试循环
                
                except Exception as e:
                    retry_count += 1
                    print(f"处理文件 {video['name']} 失败，重试 {retry_count}/{max_retries}: {str(e)}")
                    
                    if retry_count >= max_retries:
                        # 最终失败，记录失败信息
                        results.append({
                            'name': video['name'],
                            'path': video['path'],
                            'code': '',
                            'tags': '处理失败'
                        })
                    else:
                        time.sleep(self.config['llm']['delay'] * 2)
            
        return results

    def export_to_excel(self, results, output_path):
        """导出结果到Excel"""
        df = pd.DataFrame(results)
        df.to_excel(output_path, index=False)

if __name__ == "__main__":
    # 测试代码
    import yaml
    
    with open('config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
        
    processor = VideoProcessor(config)
    
    # 测试文件名提取
    test_filename = "MIDV-960 初体験3SEX 瞬イキ敏感娘ビクッ！ビクッ！性感開発 輝星きら"
    code = processor.extract_code(test_filename)
    print(f"提取的番号: {code}")
    
    # 测试标签获取
    if code:
        tags = processor.fetch_tags(code)
        print(f"获取的标签: {tags}") 