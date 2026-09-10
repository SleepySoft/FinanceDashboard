/**
 * powbox/solver.js — POW 求解器：Web Worker 后台计算 + 进度/测速/取消。
 * 求解目标：sha256(`${challenge}:${sha256Hex(content)}:${nonce}`) 前 difficulty 个 bit 为 0。
 * 零依赖；Worker 源码由 sha256Hex / leadingZeroBits 的函数体现场拼接，单文件可拷走复用。
 */
import { sha256Hex, leadingZeroBits } from './sha256.js'

const BATCH = 8192

function buildWorkerSource() {
  return `
    const sha256Hex = ${sha256Hex.toString()};
    const leadingZeroBits = ${leadingZeroBits.toString()};
    onmessage = (e) => {
      const { challenge, contentHash, difficulty } = e.data;
      const t0 = Date.now();
      let nonce = 0;
      for (;;) {
        for (let i = 0; i < ${BATCH}; i++, nonce++) {
          const h = sha256Hex(challenge + ':' + contentHash + ':' + nonce);
          if (leadingZeroBits(h) >= difficulty) {
            postMessage({ type: 'found', nonce, elapsed: Date.now() - t0 });
            return;
          }
        }
        postMessage({ type: 'progress', hashes: nonce, elapsed: Date.now() - t0 });
      }
    };
  `
}

/**
 * 求解 POW。返回 { promise, cancel }。
 * promise resolve: { nonce, difficulty, hashes, elapsedMs, rate }
 * onProgress({ hashes, elapsedMs, rate }) 每个批次回调一次。
 */
export function solvePow({ challenge, content, difficulty, onProgress }) {
  const contentHash = sha256Hex(content)

  // 无 Worker 环境的降级：主线程分批计算，批间让出事件循环避免卡死 UI
  if (typeof Worker === 'undefined') {
    let cancelled = false
    const promise = (async () => {
      const t0 = Date.now()
      let nonce = 0
      for (;;) {
        if (cancelled) throw new Error('已取消')
        for (let i = 0; i < BATCH; i++, nonce++) {
          const h = sha256Hex(`${challenge}:${contentHash}:${nonce}`)
          if (leadingZeroBits(h) >= difficulty) {
            const elapsedMs = Date.now() - t0
            return { nonce, difficulty, hashes: nonce + 1, elapsedMs, rate: (nonce + 1) / (elapsedMs / 1000 || 1) }
          }
        }
        const elapsedMs = Date.now() - t0
        onProgress?.({ hashes: nonce, elapsedMs, rate: nonce / (elapsedMs / 1000 || 1) })
        await new Promise(r => setTimeout(r, 0))
      }
    })()
    return { promise, cancel: () => { cancelled = true } }
  }

  const url = URL.createObjectURL(new Blob([buildWorkerSource()], { type: 'application/javascript' }))
  const worker = new Worker(url)
  let settled = false
  let rejectFn = null
  const cleanup = () => { worker.terminate(); URL.revokeObjectURL(url) }
  const promise = new Promise((resolve, reject) => {
    rejectFn = reject
    worker.onmessage = (e) => {
      const m = e.data
      if (m.type === 'progress') {
        onProgress?.({ hashes: m.hashes, elapsedMs: m.elapsed, rate: m.hashes / (m.elapsed / 1000 || 1) })
      } else if (m.type === 'found') {
        settled = true
        cleanup()
        resolve({
          nonce: m.nonce,
          difficulty,
          hashes: m.nonce + 1,
          elapsedMs: m.elapsed,
          rate: (m.nonce + 1) / (m.elapsed / 1000 || 1),
        })
      }
    }
    worker.onerror = () => {
      settled = true
      cleanup()
      reject(new Error('POW 计算出错'))
    }
  })
  worker.postMessage({ challenge, contentHash, difficulty })
  return {
    promise,
    cancel: () => {
      if (settled) return
      settled = true
      cleanup()
      rejectFn?.(new Error('已取消'))
    },
  }
}
