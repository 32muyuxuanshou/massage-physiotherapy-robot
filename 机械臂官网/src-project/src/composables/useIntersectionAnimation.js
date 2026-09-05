// src/composables/useIntersectionAnimation.js
import { ref, onBeforeUnmount } from 'vue'

export function useIntersectionAnimation(options = {}) {
  const elementVisible = ref(false)
  let observer = null

  const defaultOptions = {
    threshold: 0.3,
    rootMargin: '0px 0px -50px 0px',
    delay: 0,
  }

  const opts = { ...defaultOptions, ...options }

  const initAnimation = (elementRef) => {
    if (!elementRef || !elementRef.value) return

    observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            if (opts.delay > 0) {
              setTimeout(() => {
                elementVisible.value = true
              }, opts.delay)
            } else {
              elementVisible.value = true
            }
            observer.unobserve(entry.target)
          }
        })
      },
      {
        threshold: opts.threshold,
        rootMargin: opts.rootMargin,
      }
    )

    observer.observe(elementRef.value)
  }

  onBeforeUnmount(() => {
    if (observer) {
      observer.disconnect()
    }
  })

  return {
    elementVisible,
    initAnimation,
  }
}
