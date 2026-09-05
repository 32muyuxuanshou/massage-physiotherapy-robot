<template>
  <div class="contact-view">
    <div class="container">
      <div class="row justify-content-center align-items-center">
        <div
          class="display-2 text-center mb-5 text-white fw-bold contact-title"
          style="margin-top: 3em"
        >
          联系我们
        </div>
        <p class="fs-5 text-center mb-5 contact-text">我们致力于为用户提供专业的、定制化解决方案</p>

        <!-- 表单区域 -->
        <div class="row justify-content-center mb-5">
          <div class="col-lg-10 col-md-12 col-sm-12">
            <form
              @submit.prevent="handleSubmit"
              class="bg-white p-4 rounded-4 shadow-lg border p-5"
            >
              <!-- 第一行：姓名、国家、联系方式 -->
              <div class="row g-3 mb-3">
                <div class="col-md-4">
                  <label for="name" class="form-label text-muted fs-6">姓名*</label>
                  <input
                    type="text"
                    id="name"
                    v-model="formData.name"
                    class="form-control form-control-sm"
                    placeholder="请输入您的姓名"
                    required
                  />
                </div>
                <div class="col-md-4">
                  <label for="country" class="form-label text-muted fs-6">国家/地区*</label>
                  <input
                    type="text"
                    id="country"
                    v-model="formData.country"
                    class="form-control form-control-sm"
                    placeholder="所属国家或地区"
                    required
                  />
                </div>
                <div class="col-md-4">
                  <label for="phone" class="form-label text-muted fs-6">联系方式*</label>
                  <input
                    type="tel"
                    id="phone"
                    v-model="formData.phone"
                    class="form-control form-control-sm"
                    placeholder="请输入手机号"
                    required
                  />
                </div>
              </div>

              <!-- 第二行：公司、邮箱 -->
              <div class="row g-3 mb-3">
                <div class="col-md-6">
                  <label for="company" class="form-label text-muted fs-6">公司</label>
                  <input
                    type="text"
                    id="company"
                    v-model="formData.company"
                    class="form-control form-control-sm"
                    placeholder="请输入公司名称"
                  />
                </div>
                <div class="col-md-6">
                  <label for="email" class="form-label text-muted fs-6">邮箱*</label>
                  <input
                    type="email"
                    id="email"
                    v-model="formData.email"
                    class="form-control form-control-sm"
                    placeholder="请输入邮箱地址"
                    required
                  />
                </div>
              </div>

              <!-- 联系地址 -->
              <div class="mb-3">
                <label for="address" class="form-label text-muted fs-6">联系地址</label>
                <input
                  type="text"
                  id="address"
                  v-model="formData.address"
                  class="form-control form-control-sm"
                  placeholder="请输入您的联系地址"
                />
              </div>

              <!-- 内容 -->
              <div class="mb-3">
                <label for="content" class="form-label text-muted fs-6">内容*</label>
                <textarea
                  id="content"
                  v-model="formData.content"
                  class="form-control form-control-sm"
                  rows="5"
                  placeholder="所填内容请务必包含产品名称或型号"
                  required
                ></textarea>
              </div>

              <!-- 验证码 -->
              <div class="mb-3 align-items-center gap-2">
                <label for="captcha" class="form-label text-muted fs-6">验证码*</label>
                <div class="d-flex align-items-center gap-2 mb-2">
                  <input
                    type="text"
                    id="captcha"
                    v-model="formData.captcha"
                    class="form-control form-control-sm flex-grow-1"
                    placeholder="请输入验证码"
                    required
                  />
                  <img
                    :src="captchaImage"
                    alt="验证码"
                    class="captcha-img"
                    @click="refreshCaptcha"
                    style="cursor: pointer; height: 30px"
                  />
                </div>
              </div>

              <!-- 同意条款 -->
              <div class="mb-3">
                <small class="text-muted">
                  通过提交此表单，即表示您同意我们的使用条款和隐私政策。隐私政策阐述了我们将如何收集、使用及披露您的个人信息，包括向第三方披露的情形。
                </small>
              </div>

              <!-- 提交按钮 -->
              <button type="submit" class="btn btn-primary w-100">联系销售</button>
            </form>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

// 表单数据
const formData = ref({
  name: '',
  country: '',
  phone: '',
  company: '',
  email: '',
  address: '',
  content: '',
  captcha: '',
})

// 验证码图片 URL（模拟）
const captchaImage = ref('https://galaxea-ai.com/images/captcha/WO4O.png')

// 刷新验证码
const refreshCaptcha = () => {
  // 这里可以替换为真实接口生成新验证码
  captchaImage.value =
    'https://galaxea-ai.com/images/captcha/' + Math.random().toString(36).substring(2, 8) + '.png'
}

// 提交表单
const handleSubmit = () => {
  console.log('表单提交:', formData.value)
  // 这里可以发送到后端 API
}
</script>

<style scoped>
.contact-view {
  background: url('https://galaxea-ai.com/images/contact/background.png') no-repeat top center;
  background-size: 100% auto;
  min-height: 100vh;
}

.contact-text {
  color: #99a1af;
}

.form-control-sm {
  font-size: 0.875rem;
}

.captcha-img {
  width: 80px;
  height: 40px;
  object-fit: contain;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn {
  font-weight: 500;
  padding: 0.75rem 1rem;
}

@media screen and (max-width: 768px) {
  .contact-title {
    font-size: 2.5rem;
    margin-top: 2em !important;
  }
}
</style>
