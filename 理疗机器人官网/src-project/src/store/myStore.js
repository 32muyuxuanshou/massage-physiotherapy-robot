// src/store/myStore.js
import { defineStore } from 'pinia'

export const useMyStore = defineStore({
  id: 'myStore',
  // defineStore('myStore',{})  myStore就是这个仓库的名称name
  state: () => ({
    username: '赫赫',
    age: 30,
    like: 'girl',
    obj: { money: 100, friend: 10 },
    hobby: [
      { id: 1, name: '篮球', level: 1 },
      { id: 2, name: 'rap', level: 10 },
    ],
  }),
  getters: {
    // 类似于计算属性，参数state指向defineStore下的state
    doubleAge(state) {
      return state.age * 2
    },
    //在getter中 使用另一个getter  this指向当前存储库
    addOneAge() {
      return this.doubleAge + 1
    },
    //返回一个函数
    returnFunction(state) {
      return function (id) {
        return state.hobby.find((item) => item.id == id)
      }
    },
  },
  //可以通过this访问整个store实例的所有操作，支持异步操作
  actions: {
    //非异步操作
    addAge(e) {
      console.log('接受的数据', e) //e是外部调用方法传递的参数
      this.age = this.age + e
    },
    // 模拟异步
    asynchronous() {
      return new Promise((resolve) => {
        setTimeout(() => {
          resolve('模拟异步返回值')
        }, 2000)
      })
    },
    // 异步操作
    async getList() {
      const res = await this.asynchronous()
      console.log(res)
    },
  },
})
