import type { LocationSubmission } from './types'

const DATABASE = 'transitops-tracking'
const STORE = 'pending-locations'

const database = () => new Promise<IDBDatabase>((resolve, reject) => {
  const request = indexedDB.open(DATABASE, 1)
  request.onupgradeneeded = () => {
    if (!request.result.objectStoreNames.contains(STORE)) request.result.createObjectStore(STORE, { keyPath: 'idempotency_key' })
  }
  request.onsuccess = () => resolve(request.result)
  request.onerror = () => reject(request.error)
})

export const queueLocation = async (point: LocationSubmission) => {
  const db = await database()
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, 'readwrite')
    transaction.objectStore(STORE).put(point)
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
  db.close()
}

export const pendingLocations = async () => {
  const db = await database()
  const values = await new Promise<LocationSubmission[]>((resolve, reject) => {
    const request = db.transaction(STORE, 'readonly').objectStore(STORE).getAll()
    request.onsuccess = () => resolve(request.result.sort((a, b) => a.captured_at.localeCompare(b.captured_at)))
    request.onerror = () => reject(request.error)
  })
  db.close()
  return values
}

export const removePendingLocations = async (keys: string[]) => {
  const db = await database()
  await new Promise<void>((resolve, reject) => {
    const transaction = db.transaction(STORE, 'readwrite')
    keys.forEach((key) => transaction.objectStore(STORE).delete(key))
    transaction.oncomplete = () => resolve()
    transaction.onerror = () => reject(transaction.error)
  })
  db.close()
}
