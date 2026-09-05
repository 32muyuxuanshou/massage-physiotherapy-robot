<template>
  <section class="contact-section" id="contact">
    <div class="container">
      <div class="row gy-4">
        <!-- 左侧表单区域 -->
        <div class="col-lg-6">
          <div class="contact-form-wrapper">
            <h2 class="section-title">联系我们</h2>
            <p class="section-description">
              我们期待与您交流，为您解答关于我们易启未来机器人产品的任何疑问，并共同探索科技健康领域的无限可能。
            </p>

            <form @submit.prevent="handleSubmit">
              <!-- 公司名称输入框 -->
              <div class="form-group mb-2">
                <input
                  type="text"
                  class="form-control"
                  placeholder="请输入您所在的公司"
                  v-model="formData.company"
                  required
                />
              </div>

              <!-- 联系人名称输入框 -->
              <div class="form-group mb-2">
                <input
                  type="text"
                  class="form-control"
                  placeholder="请输入联系人名称"
                  v-model="formData.contactName"
                  required
                />
              </div>

              <!-- 手机号输入框 -->
              <div class="form-group mb-2">
                <input
                  type="tel"
                  class="form-control"
                  placeholder="请输入您的手机号"
                  v-model="formData.phone"
                  required
                />
              </div>

              <!-- 验证码输入框 -->
              <div class="form-group mb-2">
                <div class="captcha-container">
                  <input
                    type="text"
                    class="form-control captcha-input"
                    placeholder="请输入验证码"
                    v-model="formData.captcha"
                    required
                  />
                  <img
                    :src="captchaImage"
                    alt="验证码"
                    class="captcha-image"
                    @click="refreshCaptcha"
                  />
                </div>
              </div>

              <!-- 行业选择输入框 -->
              <div class="form-group mb-2">
                <input
                  type="text"
                  class="form-control"
                  placeholder="请输入所属行业"
                  v-model="formData.industry"
                  required
                />
              </div>

              <!-- 咨询类型选择框 -->
              <div class="form-group mb-2">
                <select class="form-control" v-model="formData.consultationType" required>
                  <option value="">请选择咨询类型</option>
                  <option value="合作咨询">合作咨询</option>
                  <option value="产品咨询">产品咨询</option>
                  <option value="技术支持">技术支持</option>
                  <option value="其他">其他</option>
                </select>
              </div>

              <!-- 提交按钮 -->
              <button type="submit" class="btn-submit">提交信息</button>
            </form>

            <!-- 官方服务热线 -->
            <div class="service-hotline">易启未来机器人官方服务热线：400-007-0163</div>
          </div>
        </div>

        <!-- 右侧图片区域 -->
        <div class="col-lg-6">
          <div class="image-container">
            <img
              src="https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/us.png"
              alt="联系我们"
              class="contact-image"
            />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

// 表单数据
const formData = ref({
  company: '',
  contactName: '',
  phone: '',
  captcha: '',
  industry: '',
  consultationType: '',
})

// 验证码相关
const captchaImage = ref(
  'https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/captcha.png'
)
const captchaCode = ref('N386A')

// 刷新验证码
const refreshCaptcha = () => {
  // 这里可以生成新的验证码
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let code = ''
  for (let i = 0; i < 5; i++) {
    code += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  captchaCode.value = code
  captchaImage.value = `https://static.fuxi.netease.com/massage-robot/avatarkit/Product-Card/official-website/captcha-${code}.png`
}

// 提交表单
const handleSubmit = () => {
  // 这里可以添加表单验证逻辑
  if (!formData.value.captcha || formData.value.captcha !== captchaCode.value) {
    alert('验证码错误，请重新输入')
    return
  }

  // 发送表单数据到服务器
  console.log('表单数据:', formData.value)

  // 清空表单
  formData.value = {
    company: '',
    contactName: '',
    phone: '',
    captcha: '',
    industry: '',
    consultationType: '',
  }

  // 刷新验证码
  refreshCaptcha()

  alert('提交成功！我们会尽快与您联系。')
}
</script>

<style scoped>
.contact-section {
  padding: 80px 0;
  background-color: #f5f5f5;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
}

.row {
  display: flex;
  flex-wrap: wrap;
  align-items: stretch; /* 关键：拉伸子元素高度一致 */
}

.col-lg-6,
.col-md-12 {
  width: 100%;
  padding: 0 15px;
}

@media (min-width: 992px) {
  .col-lg-6 {
    width: 50%;
  }
}

.contact-form-wrapper {
  background-color: white;
  padding: 40px;
  border-radius: 8px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.section-title {
  font-size: 28px;
  font-weight: bold;
  color: #333;
  margin-bottom: 15px;
}

.section-description {
  color: #666;
  font-size: 14px;
  line-height: 1.5;
  margin-bottom: 30px;
}

.form-group {
}

.form-control {
  width: 100%;
  padding: 12px 15px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.3s ease;
}

.form-control:focus {
  outline: none;
  border-color: #0056e0;
  box-shadow: 0 0 0 3px rgba(0, 86, 224, 0.1);
}

.captcha-container {
  display: flex;
  gap: 10px;
  align-items: center;
}

.captcha-input {
  flex: 1;
}

.captcha-image {
  width: 100px;
  height: 40px;
  cursor: pointer;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-submit {
  background-color: #0056e0;
  color: white;
  border: none;
  padding: 12px 30px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s ease;
  width: 100%;
}

.btn-submit:hover {
  background-color: #0040c0;
}

.service-hotline {
  color: #666;
  font-size: 14px;
  margin-top: 20px;
  text-align: center;
}

.image-container {
  position: relative;
  overflow: hidden;
  border-radius: 8px;
  height: 100%;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.contact-image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 响应式设计 */
@media (max-width: 991px) {
  .contact-form-wrapper {
    padding: 30px;
  }

  .section-title {
    font-size: 24px;
  }
}

@media (max-width: 767px) {
  .contact-form-wrapper {
    padding: 20px;
  }

  .section-title {
    font-size: 22px;
  }

  .section-description {
    font-size: 13px;
  }
}
</style>
