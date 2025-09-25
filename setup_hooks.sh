#!/bin/bash
# 设置脚本，用于初始化项目、安装依赖并配置 Husky pre-push 钩子

echo "--- 1. 初始化 npm 项目 (如果 package.json 不存在) ---"
if [ ! -f package.json ]; then
  npm init -y
fi

echo "--- 2. 安装依赖 ---"
# 安装 husky 用于 git hooks
npm install --save-dev husky
# 安装 python-dotenv 用于从 .env 文件加载密钥
pip install python-dotenv

echo "--- 3. 启用 Husky ---"
npx husky init

echo "--- 4. 创建 pre-push 钩子 ---"
# 创建 pre-push 钩子文件，并写入需要执行的命令
# 1. 运行翻译脚本
# 2. 如果脚本成功，将翻译后的文件添加到暂存区
# 3. `exit 0` 确保即使没有文件被添加，钩子也能成功退出，从而让 push 继续
cat > .husky/pre-push << EOL
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

echo "Husky pre-push: 正在运行文档翻译脚本..."
python scripts/translate_docs.py
echo "翻译脚本执行完毕。"

echo "将更新后的翻译文件添加到提交中..."
git add zh-Hans/**/*.mdx

echo "Pre-push 钩子执行完毕。"
exit 0
EOL

# 赋予钩子文件可执行权限
chmod +x .husky/pre-push

echo "--- 5. 创建 .env 文件并添加到 .gitignore ---"
# 创建 .env 文件模板
if [ ! -f .env ]; then
  echo "OPENAI_API_KEY=\"在此处粘贴您的 OpenAI API 密钥\"" > .env
  echo "已创建 .env 文件，请填入您的 API 密钥。"
fi

# 将 .env 添加到 .gitignore 以免被提交
if ! grep -q ".env" .gitignore; then
  echo "" >> .gitignore
  echo "# 存储本地环境变量，不应提交到仓库" >> .gitignore
  echo ".env" >> .gitignore
  echo "已将 .env 添加到 .gitignore"
fi

echo "--- ✅ 设置完成！ ---"
echo "请记得在 .env 文件中填入您的 OpenAI API 密钥。"
echo "现在，当您运行 'git push' 时，翻译脚本将自动执行。"
