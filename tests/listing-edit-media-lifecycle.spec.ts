import { expect, test } from '@playwright/test'

test('scoped edit draft media survives orphan cleanup while real orphans are removed', async ({ page }) => {
  await page.goto('/#/')
  await page.evaluate(() => localStorage.clear())

  const references = await page.evaluate(() => new Promise<{ edit: string; orphan: string }>((resolve, reject) => {
    const open = indexedDB.open('112233-media', 1)
    open.onupgradeneeded = () => {
      if (!open.result.objectStoreNames.contains('media')) open.result.createObjectStore('media')
    }
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const database = open.result
      const transaction = database.transaction('media', 'readwrite')
      const store = transaction.objectStore('media')
      const suffix = `${Date.now()}-${Math.random().toString(36).slice(2)}`
      const editId = `edit-draft-${suffix}`
      const orphanId = `orphan-${suffix}`
      store.put(new Blob(['edit'], { type: 'image/png' }), editId)
      store.put(new Blob(['orphan'], { type: 'image/png' }), orphanId)
      transaction.oncomplete = () => {
        database.close()
        resolve({ edit: `idb-media:${editId}`, orphan: `idb-media:${orphanId}` })
      }
      transaction.onerror = () => { database.close(); reject(transaction.error) }
    }
  }))

  await page.evaluate(({ edit }) => {
    localStorage.setItem('112233:listing-edit-draft:v1:listing-under-edit', JSON.stringify({
      version: 3,
      ownerUserId: 'host-demo',
      listingId: 'listing-under-edit',
      data: { images: [edit] },
    }))
  }, references)

  await page.reload()

  await expect.poll(() => page.evaluate(({ edit, orphan }) => new Promise<[boolean, boolean]>((resolve, reject) => {
    const open = indexedDB.open('112233-media', 1)
    open.onerror = () => reject(open.error)
    open.onsuccess = () => {
      const database = open.result
      const store = database.transaction('media', 'readonly').objectStore('media')
      const editRequest = store.get(edit.slice('idb-media:'.length))
      const orphanRequest = store.get(orphan.slice('idb-media:'.length))
      let editExists = false
      let orphanExists = false
      let completed = 0
      const finish = () => {
        completed += 1
        if (completed === 2) {
          database.close()
          resolve([editExists, orphanExists])
        }
      }
      editRequest.onsuccess = () => { editExists = editRequest.result instanceof Blob; finish() }
      editRequest.onerror = () => { database.close(); reject(editRequest.error) }
      orphanRequest.onsuccess = () => { orphanExists = orphanRequest.result instanceof Blob; finish() }
      orphanRequest.onerror = () => { database.close(); reject(orphanRequest.error) }
    }
  }), references)).toEqual([true, false])
})
