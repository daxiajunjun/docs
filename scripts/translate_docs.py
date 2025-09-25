import os
import subprocess
import openai
import json
from dotenv import load_dotenv

from openai import AzureOpenAI

# 加载 .env 文件中的环境变量
load_dotenv()

# --- 配置 ---
# 从环境变量中获取 OpenAI API 密钥
api_key = os.getenv("OPENAI_API_KEY")
azure_openai_base_url = 'https://azureopenai-east-us.openai.azure.com'
azure_openai_api_version = '2025-04-01-preview'

if not api_key:
    raise ValueError("OPENAI_API_KEY 环境变量未设置。")

client = AzureOpenAI(
            azure_endpoint=azure_openai_base_url,
            api_key=api_key,
            api_version=azure_openai_api_version,
        )

# 定义源语言和目标语言目录
SOURCE_LANGUAGE_DIRS = ['.', 'essentials']
# 在这里添加您所有需要翻译的目标语言！
TARGET_LANGUAGES = ['zh-Hans', 'fr', 'pt']
MODEL = "gpt-4o-mini" # 建议使用更新的模型以获得更好的翻译质量

# --- 辅助数据 ---
LANGUAGE_NAMES = {
    'zh-Hans': '简体中文',
    'fr': '法语',
    'pt': '葡萄牙语',
    'de': '德语'
    # 如果您添加了新的语言，可以在这里添加对应的语言名称，以便生成更清晰的指令
}

# --- 脚本逻辑 ---

def get_all_source_files():
    """遍历源目录，返回所有 .mdx 文件的列表。"""
    all_files = []
    # 确保我们处理的是绝对路径，以避免混淆
    root_path = os.path.abspath('.')
    
    for source_dir in SOURCE_LANGUAGE_DIRS:
        # 处理根目录 '.' 的情况
        if source_dir == '.':
            for item in os.listdir(root_path):
                if os.path.isfile(os.path.join(root_path, item)) and item.endswith('.mdx'):
                    all_files.append(item)
        # 处理其他子目录
        elif os.path.isdir(source_dir):
            for dirpath, _, filenames in os.walk(source_dir):
                for filename in filenames:
                    if filename.endswith('.mdx'):
                        # 保持相对路径格式
                        full_path = os.path.join(dirpath, filename)
                        all_files.append(full_path)
                        
    print(f"扫描到所有源文件: {all_files}")
    return all_files

def get_target_languages_from_config():
    """从 docs.json 文件动态读取目标语言列表"""
    config_path = 'docs.json'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        languages = [lang['language'] for lang in config.get('navigation', {}).get('languages', [])]
        
        # 移除源语言 'en'，剩下的就是目标语言
        target_languages = [lang for lang in languages if lang != 'en']
        
        if not target_languages:
            print("警告：在 docs.json 中没有找到除 'en' 之外的目标语言。")
            return []
            
        print(f"从 docs.json 中成功加载目标语言: {target_languages}")
        return target_languages
        
    except FileNotFoundError:
        print(f"错误: {config_path} 文件未找到。")
        return []
    except (json.JSONDecodeError, KeyError) as e:
        print(f"错误: 解析 {config_path} 时出错 - {e}")
        return []

def filter_source_files(file_list):
    """一个辅助函数，用于从文件列表中筛选出我们关心的源文件。"""
    source_files = []
    for f in file_list:
        # 确保 f 是字符串
        if not isinstance(f, str):
            continue
        if not f.endswith('.mdx'):
            continue
        # 修正后的过滤逻辑:
        # 1. 文件在根目录 (不包含 '/')
        # 2. 或文件在 'essentials/' 目录
        if '/' not in f or f.startswith('essentials/'):
            source_files.append(f)
    return source_files

def get_changed_files():
    """
    智能检测变更的 .mdx 文件列表，适配 pre-commit 和 pre-push 场景。
    返回一个元组 (changed_files, diff_base)，其中 diff_base 是 'HEAD' 或 'HEAD~1'。
    """
    # 1. 检查暂存区 (pre-commit / 手动运行场景)
    try:
        staged_result = subprocess.run(
            ['git', 'diff', '--name-only', '--cached'],
            check=True, capture_output=True, text=True
        )
        staged_files = staged_result.stdout.strip().split('\n')
        staged_files = [f for f in staged_files if f] # 过滤掉空字符串
        
        if staged_files:
            source_files = filter_source_files(staged_files)
            if source_files:
                print(f"检测到暂存区有变更 (pre-commit 模式): {source_files}")
                return source_files, 'HEAD'
    except subprocess.CalledProcessError as e:
        print(f"检查暂存区时出错: {e}")

    # 2. 如果暂存区没有，检查上一个 commit (pre-push 场景)
    try:
        pushed_result = subprocess.run(
            ['git', 'diff', '--name-only', 'HEAD~1', 'HEAD'],
            check=True, capture_output=True, text=True
        )
        pushed_files = pushed_result.stdout.strip().split('\n')
        pushed_files = [f for f in pushed_files if f] # 过滤掉空字符串

        if pushed_files:
            source_files = filter_source_files(pushed_files)
            if source_files:
                print(f"检测到上一个 commit 有变更 (pre-push 模式): {source_files}")
                return source_files, 'HEAD~1'
    except subprocess.CalledProcessError as e:
        print(f"检查上一个 commit 时出错: {e}")
        
    return [], None

def get_file_content_from_commit(commit_hash, file_path):
    """从指定的 commit 获取文件内容"""
    try:
        result = subprocess.run(
            ['git', 'show', f'{commit_hash}:{file_path}'],
            check=True,
            capture_output=True,
            text=True
        )
        return result.stdout
    except subprocess.CalledProcessError:
        # 如果文件在旧的 commit 中不存在（例如，一个新文件），则返回空字符串
        return ""

def translate_and_update(original_path, old_content, new_content, target_language):
    """调用 OpenAI API 翻译文件内容并更新目标文件"""
    target_path = os.path.join(target_language, original_path)

    # 检查目标语言的目录是否存在，如果不存在则创建它
    target_dir = os.path.dirname(target_path)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        print(f"创建了目标目录: {target_dir}")

    existing_translation = ""
    if os.path.exists(target_path):
        with open(target_path, 'r', encoding='utf-8') as f:
            existing_translation = f.read()
    else:
        print(f"目标文件 {target_path} 不存在，将创建新翻译。")


    language_name = LANGUAGE_NAMES.get(target_language, target_language)

    # --- 精心设计的 Prompt ---
    system_prompt = f"""
    你是一个专业的科技文档翻译员。你的任务是根据英文文档的变更，智能地更新对应的{language_name}翻译。
    - 你会收到三个部分的文本：旧的英文原文、新的英文原文、以及现有的{language_name}翻译。
    - 你的目标是找出新旧英文原文之间的差异，并将这些差异应用到{language_name}翻译上。
    - 保持翻译的风格和术语与现有的{language_name}翻译一致。
    - 如果英文原文是全新的（旧的英文原文为空），请将新的英文原文完整翻译成{language_name}。
    - 如果现有的翻译为空，也请将新的英文原文完整翻译成{language_name}。
    - 不要重新翻译整个文档，只更新发生变化的部分。
    - 如果英文原文中有些部分没有变化，{language_name}翻译中对应的部分也应该保持不变。
    - 最终，你只需要输出更新后的、完整的{language_name}文档内容，不要包含任何额外的解释或标记。
    """
    
    user_prompt = f"""
    请根据以下英文文档的变更，更新相应的{language_name}翻译。

    --- [旧的英文原文] ---
    {old_content}

    --- [新的英文原文] ---
    {new_content}

    --- [现有的{language_name}翻译（需要更新）] ---
    {existing_translation}
    """

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        updated_translation = response.choices[0].message.content

        # 将更新后的内容写回文件
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(updated_translation)
        
        print(f"成功更新文件: {target_path}")
        return target_path  # 返回成功更新的文件路径

    except Exception as e:
        print(f"调用 OpenAI API 或写入文件时出错: {e}")
        return None


def main():
    """主函数"""
    target_languages = get_target_languages_from_config()
    if not target_languages:
        print("没有可用的目标语言，脚本终止。")
        return

    all_source_files = get_all_source_files()
    changed_source_files, diff_base = get_changed_files()
    
    tasks = []
    
    # 智能识别需要处理的任务
    for source_file in all_source_files:
        for target_language in target_languages:
            target_path = os.path.join(target_language, source_file)
            
            # 任务1：如果翻译文件不存在，则需要创建
            if not os.path.exists(target_path):
                tasks.append({'type': 'create', 'source': source_file, 'lang': target_language})
            # 任务2：如果源文件在检测到的变更列表中，则需要更新
            elif source_file in changed_source_files:
                tasks.append({'type': 'update', 'source': source_file, 'lang': target_language})

    if not tasks:
        print("没有检测到需要创建或更新的翻译文件。")
        return
        
    print(f"识别到 {len(tasks)} 个翻译任务...")
    successfully_updated_files = []
    
    # 执行任务
    for task in tasks:
        source_file = task['source']
        target_language = task['lang']
        
        print(f"正在执行任务 [{task['type']}] -> {source_file} ({target_language})")
        
        with open(source_file, 'r', encoding='utf-8') as f:
            new_content = f.read()
            
        old_content = ""
        # 只有“更新”任务才需要获取旧的原文内容
        if task['type'] == 'update':
            # 根据检测到的模式，从正确的基准获取旧内容
            old_content = get_file_content_from_commit(diff_base, source_file)
            # 如果内容没有实际变化，则跳过，节省API调用
            if old_content == new_content:
                print(f"文件 {source_file} 内容没有实际变化，跳过更新。")
                continue
                
        updated_file_path = translate_and_update(source_file, old_content, new_content, target_language)
        if updated_file_path:
            successfully_updated_files.append(updated_file_path)
            
    # 自动将所有成功更新的文件添加到 git 暂存区
    if successfully_updated_files:
        print("正在将更新后的翻译文件添加到暂存区...")
        for file_to_add in set(successfully_updated_files): # 使用 set 去重
            try:
                subprocess.run(['git', 'add', file_to_add], check=True)
                print(f" - 已暂存: {file_to_add}")
            except subprocess.CalledProcessError as e:
                print(f"错误: 暂存文件 {file_to_add} 失败 - {e}")

if __name__ == "__main__":
    main()
