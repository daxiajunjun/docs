#!/bin/bash
# 设置脚本，用于初始化项目、安装依赖并配置 Husky pre-push 钩子

# --- 0. 环境检查 (macOS with Homebrew) ---
echo "--- 0. 正在检查所需环境 ---"

# 检查是否为 macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "⚠️  注意: 此脚本的自动环境安装功能专为 macOS 设计。"
    echo "    在非 macOS 系统上，请确保您已手动安装 Node.js 和 Python。"
else
    # 检查 Homebrew
    if ! command -v brew &> /dev/null
    then
        echo "❌ 错误: 未找到 'brew' (Homebrew) 命令。它是自动安装 Node.js 和 Python 的前提。"
        echo "   请先访问 https://brew.sh/ 按照官网指示进行安装。"
        exit 1
    fi
    echo "✅ Homebrew 已安装。"

    # 检查并安装 Node.js
    if ! brew list node &> /dev/null
    then
        echo "未检测到 Node.js，正在通过 Homebrew 安装..."
        brew install node
    else
        echo "✅ Node.js 已安装。"
    fi

    # 检查并安装 Python
    if ! brew list python &> /dev/null
    then
        echo "未检测到 Python，正在通过 Homebrew 安装..."
        brew install python
    else
        echo "✅ Python 已安装。"
    fi
fi

# 检查 npm
if ! command -v npm &> /dev/null
then
    echo "❌ 错误: 未找到 'npm' 命令。请确保 Node.js 已正确安装并位于您的 PATH 中。"
    exit 1
fi

# 检查 pip
if ! command -v pip &> /dev/null && ! command -v pip3 &> /dev/null;
then
    echo "❌ 错误: 未找到 'pip' 或 'pip3' 命令。请确保 Python 已正确安装并位于您的 PATH 中。"
    exit 1
fi

echo "✅ 基础环境依赖已就绪。"

echo "--- 1. 初始化 npm 项目 (如果 package.json 不存在) ---"
if [ ! -f package.json ]; then
  npm init -y
fi

echo "--- 2. 安装依赖 ---"
# 安装 husky 用于 git hooks
npm install --save-dev husky
npm install -g mint
# 安装 python-dotenv 用于从 .env 文件加载密钥
pip install python-dotenv
pip install openai

echo "--- 3. 启用 Husky ---"
npx husky init

echo "--- 4. 创建 pre-commit 钩子 ---"
# 创建 pre-push 钩子文件，并写入需要执行的命令
# 1. 运行翻译脚本
# 2. 如果脚本成功，将翻译后的文件添加到暂存区
# 3. `exit 0` 确保即使没有文件被添加，钩子也能成功退出，从而让 push 继续
cat > .husky/pre-commit << EOL
#!/bin/sh
. "$(dirname "$0")/_/husky.sh"

echo "Husky pre-commit: 正在运行文档翻译脚本并自动暂存变更..."
python scripts/translate_docs.py
echo "脚本执行完毕。"

exit 0

EOL

# 赋予钩子文件可执行权限
chmod +x .husky/pre-commit

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
