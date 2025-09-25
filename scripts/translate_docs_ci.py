# scripts/translate_docs_ci.py
# 专为在 GitHub Actions 环境中运行而设计的版本

import os
import sys
import subprocess
import json
import openai
from openai import AzureOpenAI

# --- 配置 ---
api_key = os.getenv("OPENAI_API_KEY")
azure_openai_base_url = 'https://azureopenai-east-us.openai.azure.com'
azure_openai_api_version = '2025-04-01-preview'

if not api_key:
    raise ValueError("一个或多个环境变量未设置 (OPENAI_API_KEY)")

client = AzureOpenAI(
    azure_endpoint=azure_openai_base_url,
    api_key=api_key,
    api_version=azure_openai_api_version,
)

SOURCE_LANGUAGE_DIRS = ['.', 'essentials']
MODEL = os.getenv("AZURE_OPENAI_MODEL", "gpt-4o-mini") # 允许通过环境变量配置模型

LANGUAGE_NAMES = {
    'zh-Hans': '简体中文', 'fr': '法语', 'pt': '葡萄牙语',
    'de': '德语', 'ja': '日语', 'es': '西班牙语',
    # 可根据需要添加更多语言
}


# --- 脚本逻辑 ---

def filter_source_files(file_list):
    """一个辅助函数，用于从文件列表中筛选出我们关心的源文件。"""
    source_files = []
    for f in file_list:
        if not isinstance(f, str) or not f.endswith('.mdx'):
            continue
        if '/' not in f or f.startswith('essentials/'):
            source_files.append(f)
    return source_files

def get_target_languages_from_config():
    # ... (此函数与本地版本完全相同) ...
    config_path = 'docs.json'
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        languages = [lang['language'] for lang in config.get('navigation', {}).get('languages', [])]
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

def get_all_source_files():
    # ... (此函数与本地版本完全相同) ...
    all_files = []
    root_path = os.path.abspath('.')
    for source_dir in SOURCE_LANGUAGE_DIRS:
        if source_dir == '.':
            for item in os.listdir(root_path):
                if os.path.isfile(os.path.join(root_path, item)) and item.endswith('.mdx'):
                    all_files.append(item)
        elif os.path.isdir(source_dir):
            for dirpath, _, filenames in os.walk(source_dir):
                for filename in filenames:
                    if filename.endswith('.mdx'):
                        full_path = os.path.join(dirpath, filename)
                        all_files.append(full_path)
    print(f"扫描到所有源文件: {all_files}")
    return all_files

def get_changed_files_in_ci(before_sha, after_sha):
    """在 CI 环境中，获取两个 commit 之间的变更文件列表"""
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', before_sha, after_sha],
            check=True, capture_output=True, text=True
        )
        changed_files = result.stdout.strip().split('\n')
        source_files = filter_source_files(changed_files)
        print(f"检测到 CI 中的源文件变更: {source_files}")
        return source_files
    except subprocess.CalledProcessError as e:
        print(f"执行 git diff 时出错: {e}")
        return []

def get_file_content_from_commit(commit_hash, file_path):
    # ... (此函数与本地版本完全相同) ...
    try:
        result = subprocess.run(['git', 'show', f'{commit_hash}:{file_path}'], check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError:
        return ""

def translate_and_update(original_path, old_content, new_content, target_language):
    # ... (此函数与本地版本几乎相同，只是没有返回路径) ...
    target_path = os.path.join(target_language, original_path)
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
        print(updated_translation)
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(updated_translation)
        print(f"成功更新文件: {target_path}")
    except Exception as e:
        print(f"调用 OpenAI API 或写入文件时出错: {e}")

def main():
    """主函数"""
    try:
        before_sha = sys.argv[1]
        after_sha = sys.argv[2]
    except IndexError:
        print("错误: 脚本需要 'before' 和 'after' 两个 commit SHA 作为参数。")
        sys.exit(1)
        
    target_languages = get_target_languages_from_config()
    if not target_languages:
        print("没有可用的目标语言，脚本终止。")
        return

    all_source_files = get_all_source_files()
    changed_source_files = get_changed_files_in_ci(before_sha, after_sha)
    
    tasks = []
    for source_file in all_source_files:
        for target_language in target_languages:
            target_path = os.path.join(target_language, source_file)
            if not os.path.exists(target_path):
                tasks.append({'type': 'create', 'source': source_file, 'lang': target_language})
            elif source_file in changed_source_files:
                tasks.append({'type': 'update', 'source': source_file, 'lang': target_language})

    if not tasks:
        print("没有检测到需要创建或更新的翻译文件。")
        return
        
    print(f"识别到 {len(tasks)} 个翻译任务...")
    
    for task in tasks:
        source_file = task['source']
        target_language = task['lang']
        print(f"正在执行任务 [{task['type']}] -> {source_file} ({target_language})")
        with open(source_file, 'r', encoding='utf-8') as f:
            new_content = f.read()
        old_content = ""
        if task['type'] == 'update':
            old_content = get_file_content_from_commit(before_sha, source_file)
            if old_content == new_content:
                print(f"文件 {source_file} 内容没有实际变化，跳过更新。")
                continue
        translate_and_update(source_file, old_content, new_content, target_language)

if __name__ == "__main__":
    main()
