# 豆瓣图书封面API - 部署到Railway.app

## 📚 功能说明

这个API服务使用Selenium绕过豆瓣反爬虫，为前端提供：
- 图书信息查询（支持ISBN和书名）
- 图书封面图片获取
- 支持中文书籍

## 🚀 部署到Railway.app

### 步骤1：注册Railway账号

1. 访问 https://railway.app/
2. 点击 "Start a New Project"
3. 选择 "Deploy from GitHub repo"

### 步骤2：上传代码

**方法A：通过GitHub（推荐）**
1. 将这个文件夹上传到你的GitHub
2. 在Railway中选择你的GitHub仓库
3. Railway会自动部署

**方法B：直接上传**
1. 在Railway项目中点击 "New Project"
2. 选择 "Deploy from CLI"
3. 按照提示安装Railway CLI
4. 运行：`railway login`
5. 在这个文件夹运行：`railway init`
6. 运行：`railway up`

### 步骤3：配置环境变量

Railway会自动安装requirements.txt中的依赖

### 步骤4：获取API地址

部署完成后，Railway会给你一个URL，例如：
```
https://your-api.railway.app
```

## 📡 API接口

### 1. 搜索图书
```
GET/POST https://your-api.railway.app/api/search?query=三体
```

返回示例：
```json
{
  "title": "三体",
  "author": ["刘慈欣"],
  "publisher": "重庆出版社",
  "rating": "9.2",
  "cover_url": "https://img3.doubanio.com/view/subject/l/public/s34863232.jpg"
}
```

### 2. 获取封面图片
```
GET https://your-api.railway.app/api/cover/9787536692930
```
直接返回图片，可用于`<img>`标签

### 3. 获取封面Base64
```
GET https://your-api.railway.app/api/cover-base64/9787536692930
```
返回JSON格式的Base64编码

## 💰 费用说明

Railway免费套餐：
- 每月$5额度
- 512MB内存
- 有限时间运行
- **完全免费，无需信用卡**

## ⚠️ 注意事项

1. **首次部署较慢**：需要下载Chrome浏览器
2. **有运行时间限制**：免费套餐会在无请求时休眠
3. **首次请求会慢**：因为需要唤醒服务

## 🔧 故障排除

如果遇到问题：
1. 查看Railway日志
2. 确认PORT环境变量正确
3. 检查ChromeDriver是否正确安装
