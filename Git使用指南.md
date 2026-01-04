# Git 使用指南 - 备份您的项目

## 📋 目录
1. [Git 是什么？](#git-是什么)
2. [安装 Git](#安装-git)
3. [首次配置 Git](#首次配置-git)
4. [初始化仓库](#初始化仓库)
5. [基本操作流程](#基本操作流程)
6. [常用命令详解](#常用命令详解)
7. [创建备份到远程仓库](#创建备份到远程仓库)
8. [日常使用建议](#日常使用建议)

---

## Git 是什么？

Git 是一个**版本控制系统**，它可以帮助您：
- ✅ **备份代码**：保存代码的历史版本
- ✅ **恢复文件**：如果代码出现问题，可以回退到之前的版本
- ✅ **追踪变更**：查看每个文件的修改历史
- ✅ **协作开发**：多人协作时管理代码变更
- ✅ **分支管理**：可以创建不同的分支进行实验

---

## 安装 Git

### Windows 系统安装步骤：

1. **下载 Git**
   - 访问：https://git-scm.com/download/win
   - 或访问：https://github.com/git-for-windows/git/releases
   - 下载最新的安装程序（如：Git-2.x.x-64-bit.exe）

2. **安装 Git**
   - 双击安装程序
   - 一路点击"下一步"（Next），使用默认设置即可
   - 安装完成后，关闭所有命令窗口

3. **验证安装**
   - 打开 PowerShell 或 CMD
   - 输入：`git --version`
   - 如果显示版本号（如：git version 2.xx.x），说明安装成功

---

## 首次配置 Git

安装完成后，需要先配置您的身份信息（只需要配置一次）：

```bash
# 配置用户名（使用您的名字）
git config --global user.name "您的名字"

# 配置邮箱（使用您的邮箱）
git config --global user.email "your.email@example.com"
```

**示例：**
```bash
git config --global user.name "张三"
git config --global user.email "zhangsan@example.com"
```

---

## 初始化仓库

在您的项目目录下初始化 Git 仓库（只需要做一次）：

```bash
# 进入项目目录
cd "d:\projects\line chart"

# 初始化 Git 仓库
git init
```

这会在项目目录下创建一个 `.git` 隐藏文件夹，用于存储 Git 的所有信息。

---

## 基本操作流程

日常使用 Git 的流程非常简单，只有 3 个主要步骤：

### 1. 查看状态（了解当前情况）
```bash
git status
```
显示哪些文件被修改了、新增了、或者需要提交。

### 2. 添加到暂存区（准备提交）
```bash
# 添加所有文件
git add .

# 或添加特定文件
git add 文件名.py
```

### 3. 提交更改（保存版本）
```bash
git commit -m "描述这次做了什么修改"
```

**提交信息的示例：**
- `git commit -m "添加了Facebook广告数据同步功能"`
- `git commit -m "修复了时区配置的bug"`
- `git commit -m "更新了数据库表结构"`

---

## 常用命令详解

### 📁 文件操作

```bash
# 查看当前状态
git status

# 添加所有文件到暂存区
git add .

# 添加特定文件
git add dashboard.py

# 添加多个文件
git add file1.py file2.py

# 提交更改
git commit -m "您的提交说明"

# 查看提交历史
git log

# 查看简化的提交历史（一行显示）
git log --oneline

# 查看文件的修改内容
git diff

# 查看特定文件的修改
git diff dashboard.py
```

### 🔄 撤销操作

```bash
# 撤销未提交的修改（危险！会丢失修改）
git checkout -- 文件名

# 撤销已添加到暂存区的文件（保留修改）
git reset HEAD 文件名

# 撤销最后一次提交（保留修改）
git reset --soft HEAD~1
```

### 📤 远程仓库操作

```bash
# 添加远程仓库（GitHub/Gitee等）
git remote add origin https://github.com/用户名/仓库名.git

# 查看远程仓库
git remote -v

# 推送到远程仓库
git push -u origin main

# 之后可以简化为
git push

# 从远程仓库拉取更新
git pull
```

---

## 创建备份到远程仓库

为了确保代码安全，建议将代码备份到远程仓库（GitHub、Gitee等）。

### 方案一：使用 GitHub（国外，需要科学上网）

1. **创建 GitHub 账户**
   - 访问：https://github.com
   - 注册账户

2. **创建新仓库**
   - 登录后，点击右上角 "+" → "New repository"
   - 输入仓库名称（如：line-chart-project）
   - 选择 Public 或 Private
   - **不要**勾选 "Initialize this repository with a README"
   - 点击 "Create repository"

3. **连接本地仓库到 GitHub**
   ```bash
   # 添加远程仓库（替换为您的仓库地址）
   git remote add origin https://github.com/您的用户名/仓库名.git
   
   # 第一次推送
   git push -u origin main
   ```

### 方案二：使用 Gitee（国内，访问速度快，推荐）

1. **创建 Gitee 账户**
   - 访问：https://gitee.com
   - 注册账户

2. **创建新仓库**
   - 登录后，点击右上角 "+" → "新建仓库"
   - 输入仓库名称
   - 选择公开或私有
   - **不要**勾选 "使用Readme文件初始化这个仓库"
   - 点击 "创建"

3. **连接本地仓库到 Gitee**
   ```bash
   # 添加远程仓库（替换为您的仓库地址）
   git remote add origin https://gitee.com/您的用户名/仓库名.git
   
   # 第一次推送
   git push -u origin main
   ```

---

## 日常使用建议

### 推荐的提交频率

- ✅ **每天结束工作前**提交一次
- ✅ **完成一个功能后**立即提交
- ✅ **修复一个bug后**立即提交
- ✅ **重要修改前后**都提交一次

### 提交信息规范

使用清晰的中文描述，说明这次提交做了什么：

```bash
# 好的提交信息
git commit -m "添加了Facebook广告数据同步功能"
git commit -m "修复了时区转换的bug"
git commit -m "更新了数据库表结构，添加了store_timezone字段"
git commit -m "优化了数据同步性能，减少查询时间"

# 不好的提交信息（避免使用）
git commit -m "修改"
git commit -m "更新"
git commit -m "fix"
```

### 创建 .gitignore 文件

为了避免提交不必要的文件（如日志、缓存等），建议创建 `.gitignore` 文件：

```
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
*.log

# 数据库
*.db
*.sqlite

# 系统文件
.DS_Store
Thumbs.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# 日志文件
logs/
*.log
```

---

## 快速参考卡片

### 🔵 初始设置（只做一次）
```bash
git config --global user.name "您的名字"
git config --global user.email "您的邮箱"
cd "d:\projects\line chart"
git init
```

### 🟢 日常备份流程（每天使用）
```bash
# 1. 查看状态
git status

# 2. 添加所有文件
git add .

# 3. 提交更改
git commit -m "描述您的修改"

# 4. 推送到远程（如果已配置）
git push
```

### 🟡 查看历史
```bash
# 查看提交历史
git log --oneline

# 查看某个文件的修改历史
git log --oneline 文件名
```

### 🔴 恢复文件
```bash
# 查看所有提交
git log --oneline

# 恢复到某个提交版本（替换commit_id为实际的提交ID）
git checkout commit_id -- 文件名
```

---

## 常见问题

### Q: 如果我不小心删除了文件怎么办？
A: 可以使用 `git checkout HEAD -- 文件名` 恢复文件。

### Q: 如何查看某个文件的历史版本？
A: 使用 `git log --oneline 文件名` 查看历史，然后用 `git checkout commit_id -- 文件名` 恢复。

### Q: 提交后还能修改吗？
A: 可以，使用 `git commit --amend -m "新的提交信息"` 修改最后一次提交。

### Q: 如何创建分支进行实验？
A: 
```bash
# 创建并切换到新分支
git checkout -b 分支名

# 切换回主分支
git checkout main

# 查看所有分支
git branch
```

---

## 💡 总结

Git 的核心就是三个步骤：
1. **查看** (`git status`) - 了解当前状态
2. **添加** (`git add .`) - 准备要保存的文件
3. **提交** (`git commit -m "说明"`) - 保存当前版本

记住：**多提交，多备份，不怕出错！**

---

*如有问题，可以参考 Git 官方文档：https://git-scm.com/doc*



