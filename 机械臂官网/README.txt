机械臂首页
文件名：robot-main
开发环境启动 npm run dev

切换URl 文件路径 开发：.env.development 生产 .env.production

机械臂首页部署
docker build -t registry.cn-shenzhen.aliyuncs.com/eyecloud/hospital-site-2.0:robot-frontend ./
docker push registry.cn-shenzhen.aliyuncs.com/eyecloud/hospital-site-2.0:robot-frontend

通过构建后上传阿里云服务器镜像仓库进行部署。

首页：src\views\HomeView.vue
联系我们：src\views\ContactView.vue、

联系我们暂不可用 是个表单提交  需对接后台接口

当前部署在阿里云服务器上。
当前网站：https://www-test.aiforeye.cn/