文件名：physiotherapy-robot-main
开发环境启动 npm run dev

切换URl 文件路径 开发：.env.development 生产 .env.production


机器人官网首页部署
docker build -t registry.cn-shenzhen.aliyuncs.com/eyecloud/hospital-site-2.0:robot-official-website-frontend ./
docker push registry.cn-shenzhen.aliyuncs.com/eyecloud/hospital-site-2.0:robot-official-website-frontend

通过构建后上传阿里云服务器镜像仓库进行部署。

单页面首页 src\views\HomeView.vue

需更换图片资源

当前部署在阿里云服务器上。
当前官网：https://www-test2.aiforeye.cn/