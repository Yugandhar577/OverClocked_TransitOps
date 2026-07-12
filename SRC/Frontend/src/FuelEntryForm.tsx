import { FormEvent, useState } from 'react'
import type { AxiosInstance } from 'axios'
import { ChevronRight, FileText, Gauge, Upload } from 'lucide-react'

type RecordValue = Record<string, any>

const errorMessage = (error: unknown) => {
  const response = error as { response?: { data?: { detail?: string } } }
  return response.response?.data?.detail || 'The receipt could not be scanned. Enter the values manually.'
}

export function FuelEntryForm({ api, vehicles, onSave }: { api: AxiosInstance; vehicles: RecordValue[]; onSave: (payload: RecordValue) => void }) {
  const [payload, setPayload] = useState<RecordValue>(() => ({ vehicle_id: vehicles.find((vehicle) => vehicle.status === 'Available')?.id || '', logged_at: new Date().toISOString().slice(0, 10) }))
  const [fileName, setFileName] = useState('')
  const [preview, setPreview] = useState('')
  const [lastUploadType, setLastUploadType] = useState<'receipt' | 'odometer' | null>(null)
  const [scanning, setScanning] = useState(false)
  const [scanMessage, setScanMessage] = useState('')
  const [invalidFields, setInvalidFields] = useState<string[]>([])

  const set = (key: string, value: string) => {
    setPayload((current) => ({ ...current, [key]: value }))
    setInvalidFields((current) => current.filter((field) => field !== key))
  }

  const scanUpload = async (file: File, scanType: 'receipt' | 'odometer') => {
    const permitted = scanType === 'receipt' ? ['image/jpeg', 'image/png', 'application/pdf'] : ['image/jpeg', 'image/png']
    if (!permitted.includes(file.type) || file.size > 10 * 1024 * 1024) {
      setScanMessage(scanType === 'receipt' ? 'Choose a JPG, PNG, or PDF receipt under 10 MB.' : 'Choose a clear JPG or PNG odometer photo under 10 MB.')
      return
    }
    setFileName(file.name)
    setPreview(file.type.startsWith('image/') ? URL.createObjectURL(file) : '')
    setLastUploadType(scanType)
    setScanning(true)
    setScanMessage('')
    try {
      const form = new FormData()
      form.append('image', file)
      form.append('scan_type', scanType)
      const result = await api.post('/fuel/scan', form)
      const data = result.data
      if (scanType === 'receipt' && data.receiptImage) setPayload((current) => ({ ...current, receipt_image: data.receiptImage }))
      if (!data.success) {
        setScanMessage(data.error || 'The image could not be read. Enter the values manually.')
        return
      }
      const extracted = data.extractedData || {}
      const nextValues: RecordValue = {
        liters: extracted.liters,
        cost: extracted.totalAmount,
        price_per_liter: extracted.pricePerLiter,
        vendor: extracted.stationName,
        logged_at: extracted.date,
        odometer_km: extracted.odometerKm,
      }
      const invalid = Object.entries({ liters: extracted.liters, cost: extracted.totalAmount, price_per_liter: extracted.pricePerLiter, odometer_km: extracted.odometerKm })
        .filter(([, value]) => value !== null && value !== undefined && Number(value) <= 0)
        .map(([field]) => field)
      setPayload((current) => Object.fromEntries(Object.entries({ ...current, ...nextValues }).filter(([, value]) => value !== null && value !== undefined)))
      setInvalidFields(invalid)
      const requiredValues = scanType === 'receipt' ? ['liters', 'pricePerLiter', 'totalAmount'] : ['odometerKm']
      const missing = requiredValues.filter((field) => extracted[field] === null || extracted[field] === undefined)
      const label = scanType === 'receipt' ? 'Receipt' : 'Odometer'
      setScanMessage(missing.length ? label + ' scanned. Review or complete the remaining fields before saving.' : label + ' scanned. Review the pre-filled values before saving.')
    } catch (error) {
      setScanMessage(errorMessage(error))
    } finally {
      setScanning(false)
    }
  }

  const save = (event: FormEvent) => {
    event.preventDefault()
    const numeric = ['liters', 'cost', 'price_per_liter', 'odometer_km']
    const parsed = Object.fromEntries(Object.entries(payload).map(([key, value]) => [key, numeric.includes(key) && value !== '' ? Number(value) : value]))
    onSave(parsed)
  }

  const fields: [string, string, string?][] = [['liters', 'Litres', 'number'], ['price_per_liter', 'Price per litre', 'number'], ['cost', 'Total cost', 'number'], ['logged_at', 'Date', 'date'], ['odometer_km', 'Odometer (km)', 'number'], ['vendor', 'Vendor', 'text']]
  return <form className="entry-form" onSubmit={save}>
    <div className="receipt-upload full">
      <div className="scan-actions">
        <input id="fuel-receipt" className="receipt-file-input" type="file" accept="image/jpeg,image/png,application/pdf" onChange={(event) => { const file = event.target.files?.[0]; if (file) void scanUpload(file, 'receipt') }}/>
        <label className="secondary receipt-upload-button" htmlFor="fuel-receipt"><Upload size={17}/>Upload receipt</label>
        <input id="fuel-odometer" className="receipt-file-input" type="file" accept="image/jpeg,image/png" onChange={(event) => { const file = event.target.files?.[0]; if (file) void scanUpload(file, 'odometer') }}/>
        <label className="secondary receipt-upload-button" htmlFor="fuel-odometer"><Gauge size={17}/>Upload odometer</label>
      </div>
      {scanning && <span className="receipt-status">Scanning image...</span>}
      {fileName && <div className="receipt-preview">{preview ? <img src={preview} alt="Fuel log upload preview"/> : <FileText size={22}/>}<span>{lastUploadType === 'odometer' ? 'Odometer photo: ' : 'Receipt: '}{fileName}</span></div>}
      {scanMessage && <p className={scanMessage.includes('scanned.') ? 'receipt-status' : 'receipt-status receipt-error'}>{scanMessage}</p>}
    </div>
    <label>Vehicle<select value={payload.vehicle_id} onChange={(event) => set('vehicle_id', event.target.value)} required><option value="">Select vehicle</option>{vehicles.map((vehicle) => <option value={vehicle.id} key={vehicle.id}>{vehicle.name} - {vehicle.status}</option>)}</select></label>
    {fields.map(([key, label, type]) => <label key={key} className={invalidFields.includes(key) ? 'field-invalid' : ''}>{label}<input value={payload[key] ?? ''} onChange={(event) => set(key, event.target.value)} type={type || 'text'} step={type === 'number' ? '0.01' : undefined} required={['liters', 'price_per_liter', 'cost', 'odometer_km'].includes(key)}/></label>)}
    <button className="primary full" type="submit">Save record <ChevronRight size={18}/></button>
  </form>
}

