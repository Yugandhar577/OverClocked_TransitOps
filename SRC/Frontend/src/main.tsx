import React, { FormEvent, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BarChart3, CarFront, ChevronRight, ClipboardList, Fuel,
  LayoutDashboard, LogOut, Menu, Plus, Settings, ShieldCheck, Users, Wrench,
  X, CheckCircle2, AlertTriangle, Search, ArrowUpRight, Download, Bell,
  Camera, FileText, Gauge, MapPin, Pencil, Play, ChevronDown,
  ClipboardCheck, Ban, MapPinned, Navigation, Phone, Star, UserRound
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'
import { api, messageFrom } from './api'
import { FuelEntryForm } from './FuelEntryForm'

const DriverLiveTripPage = React.lazy(() => import('./tracking/DriverLiveTripPage').then((module) => ({ default: module.DriverLiveTripPage })))
const FleetTrackingPage = React.lazy(() => import('./tracking/FleetTrackingPage').then((module) => ({ default: module.FleetTrackingPage })))

type User = { id: string; name: string; email: string; role: string; driver_id?: string | null; region?: string | null }
type Session = { access_token: string; user: User }
type RecordValue = Record<string, any>

const nav = [
  { key: 'Dashboard', icon: LayoutDashboard, roles: ['Fleet Manager', 'Dispatcher', 'Safety Officer', 'Financial Analyst', 'Administrator'] },
  { key: 'Fleet', icon: CarFront, roles: ['Fleet Manager', 'Administrator'] },
  { key: 'Drivers', icon: Users, roles: ['Fleet Manager', 'Safety Officer', 'Administrator'] },
  { key: 'Trips', icon: ClipboardList, roles: ['Fleet Manager', 'Dispatcher', 'Safety Officer', 'Administrator'] },
  { key: 'Fleet Tracking', icon: MapPinned, roles: ['Fleet Manager', 'Dispatcher', 'Safety Officer', 'Administrator'] },
  { key: 'My Live Trip', icon: Navigation, roles: ['Driver'] },
  { key: 'Maintenance', icon: Wrench, roles: ['Fleet Manager', 'Administrator'] },
  { key: 'Fuel & Expenses', icon: Fuel, roles: ['Fleet Manager', 'Financial Analyst', 'Administrator'] },
  { key: 'Analytics', icon: BarChart3, roles: ['Fleet Manager', 'Financial Analyst', 'Administrator'] },
  { key: 'Settings', icon: Settings, roles: ['Fleet Manager', 'Administrator'] },
]

const statusClass = (status: string) => `status status-${status.toLowerCase().replaceAll(' ', '-')}`
const currency = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
const pathForPage: Record<string, string> = { 'Fleet Tracking': '/fleet-tracking', 'My Live Trip': '/driver/live-trip' }
const pageForPath = () => window.location.pathname === '/fleet-tracking' ? 'Fleet Tracking' : window.location.pathname === '/driver/live-trip' ? 'My Live Trip' : 'Dashboard'

function App() {
  const [session, setSession] = useState<Session | null>(() => {
    const saved = localStorage.getItem('transitops-session')
    return saved ? JSON.parse(saved) : null
  })
  const [page, setPage] = useState(pageForPath)
  const [mobileNav, setMobileNav] = useState(false)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState('')
  const [dashboard, setDashboard] = useState<RecordValue | null>(null)
  const [vehicles, setVehicles] = useState<RecordValue[]>([])
  const [drivers, setDrivers] = useState<RecordValue[]>([])
  const [trips, setTrips] = useState<RecordValue[]>([])
  const [maintenance, setMaintenance] = useState<RecordValue[]>([])
  const [finance, setFinance] = useState<RecordValue | null>(null)
  const [analytics, setAnalytics] = useState<RecordValue | null>(null)
  const [preferences, setPreferences] = useState<RecordValue | null>(null)
  const [permissionSummary, setPermissionSummary] = useState<RecordValue | null>(null)
  const [alerts, setAlerts] = useState<RecordValue>({ alerts: [], critical_count: 0 })
  const [alertPanel, setAlertPanel] = useState(false)
  const [vehicleDetail, setVehicleDetail] = useState<RecordValue | null>(null)
  const [driverDetail, setDriverDetail] = useState<RecordValue | null>(null)
  const [modal, setModal] = useState<'vehicle' | 'driver' | 'trip' | 'maintenance' | 'fuel' | 'expense' | null>(null)

  const allowedNav = useMemo(() => nav.filter((item) => session && item.roles.includes(session.user.role)), [session])

  const load = React.useCallback(async () => {
    if (!session) return
    setLoading(true)
    try {
      if (page === 'Dashboard') {
        const result = await api.get('/dashboard')
        setDashboard(result.data)
        setAlerts({ alerts: result.data.alerts || [], critical_count: (result.data.alerts || []).filter((item: RecordValue) => item.severity === 'critical').length })
      } else if (page === 'Fleet') setVehicles((await api.get('/vehicles')).data)
      else if (page === 'Drivers') setDrivers((await api.get('/drivers')).data)
      else if (page === 'Trips') {
        const results = await Promise.allSettled([api.get('/trips'), api.get('/vehicles'), api.get('/drivers')])
        if (results[0].status === 'rejected') throw results[0].reason
        setTrips(results[0].value.data)
        if (results[1].status === 'fulfilled') setVehicles(results[1].value.data)
        if (results[2].status === 'fulfilled') setDrivers(results[2].value.data)
      } else if (page === 'Maintenance') {
        const results = await Promise.allSettled([api.get('/maintenance'), api.get('/vehicles')])
        if (results[0].status === 'rejected') throw results[0].reason
        setMaintenance(results[0].value.data)
        if (results[1].status === 'fulfilled') setVehicles(results[1].value.data)
      } else if (page === 'Fuel & Expenses') setFinance((await api.get('/finance')).data)
      else if (page === 'Analytics') setAnalytics((await api.get('/analytics')).data)
      else if (page === 'Settings') {
        const [settingsResult, permissionsResult] = await Promise.all([api.get('/settings'), api.get('/auth/permissions')])
        setPreferences(settingsResult.data)
        setPermissionSummary(permissionsResult.data)
      }
      setNotice('')
    } catch (error) {
      const message = messageFrom(error)
      if (message.includes('session is invalid') || message.includes('session is expired')) {
        localStorage.removeItem('transitops-session')
        setSession(null)
        setNotice('Your session expired after the security upgrade. Please sign in again.')
      } else setNotice(message === 'Unable to save this change.' ? 'The API is not reachable. Start the FastAPI server on port 8000.' : message)
    } finally { setLoading(false) }
  }, [page, session])

  useEffect(() => { load() }, [load])

  const login = async (email: string, password: string) => {
    try {
      const result = await api.post('/auth/login', { email, password })
      localStorage.setItem('transitops-session', JSON.stringify(result.data))
      setSession(result.data); setNotice('Signed in to the seeded hackathon workspace.')
      if (result.data.user.role === 'Driver') { setPage('My Live Trip'); window.history.replaceState({}, '', '/driver/live-trip') }
    } catch (error) { throw new Error(messageFrom(error)) }
  }

  const logout = async () => { try { await api.post('/auth/logout') } catch { /* local sign-out still completes */ } localStorage.removeItem('transitops-session'); setSession(null); setPage('Dashboard'); window.history.replaceState({}, '', '/') }
  const mutate = async (work: () => Promise<unknown>, success: string): Promise<boolean> => {
    try { await work(); setModal(null); setNotice(success); await load(); return true } catch (error) { setNotice(messageFrom(error)); return false }
  }
  const openVehicle = async (vehicleId: string) => {
    try { const result = await api.get(`/vehicles/${vehicleId}`); setVehicleDetail(result.data) } catch (error) { setNotice(messageFrom(error)) }
  }
  const openDriver = (driver: RecordValue) => setDriverDetail(driver)
  const saveVehicle = (vehicleId: string, payload: RecordValue) => mutate(() => api.patch(`/vehicles/${vehicleId}`, payload), 'Vehicle profile updated.').then((saved) => saved ? openVehicle(vehicleId) : undefined)
  const renewDocument = (document: RecordValue) => {
    const reference = window.prompt(`New reference number for ${document.document_type}`, document.reference_number)
    if (reference === null) return
    const expiry = window.prompt('New expiry date (YYYY-MM-DD)', `${new Date().getFullYear() + 1}-12-31`)
    if (!expiry) return
    return mutate(() => api.post(`/vehicle-documents/${document.id}/renew`, { document_type: document.document_type, reference_number: reference, provider: document.provider, start_date: new Date().toISOString().slice(0, 10), expiry_date: expiry, cost: document.cost }), `${document.document_type} renewed.`).then((saved) => saved ? openVehicle(document.vehicle_id) : undefined)
  }

  if (!session) return <Login onLogin={login} />

  const choosePage = (target: string) => { setPage(target); setMobileNav(false); window.history.pushState({}, '', pathForPage[target] || '/') }
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
      <div className="brand"><span className="brand-mark"><ArrowUpRight size={19}/></span><span>Transit<span>Ops</span></span></div>
      <p className="workspace-label">OPERATIONS WORKSPACE</p>
      <nav>{allowedNav.map((item) => <button key={item.key} className={`nav-item ${page === item.key ? 'active' : ''}`} onClick={() => choosePage(item.key)}><item.icon size={18}/><span>{item.key}</span>{item.key === 'Dashboard' && alerts.critical_count > 0 && <b className="nav-alert-count">{alerts.critical_count}</b>}</button>)}</nav>
      <div className="sidebar-bottom"><div className="identity"><div className="avatar">{session.user.name.split(' ').map((name) => name[0]).join('')}</div><div><b>{session.user.name}</b><small>{session.user.role}</small></div></div><button className="logout" onClick={logout}><LogOut size={17}/> Sign out</button></div>
    </aside>
    {mobileNav && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <main className="main-content">
      <header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu /></button><div className="search"><Search size={17}/><input placeholder="Search fleet, drivers, trips…" /></div><div className="topbar-actions"><button className="alert-button" onClick={() => setAlertPanel(!alertPanel)} aria-label="Open compliance alerts"><Bell size={18}/>{alerts.critical_count > 0 && <b>{alerts.critical_count}</b>}</button><div className="top-user">Seeded demo data</div>{alertPanel && <AlertPanel alerts={alerts.alerts} onOpenVehicle={(id: string) => { setAlertPanel(false); choosePage('Fleet'); openVehicle(id) }}/>}</div></header>
      <section className="content">
        {notice && <div className="notice"><span>{notice}</span><button onClick={() => setNotice('')}><X size={16}/></button></div>}
        {loading ? <Loading /> : <Page page={page} dashboard={dashboard} vehicles={vehicles} drivers={drivers} trips={trips} maintenance={maintenance} finance={finance} analytics={analytics} preferences={preferences} permissionSummary={permissionSummary} alerts={alerts.alerts} user={session.user} onNavigate={choosePage} onAdd={setModal} onOpenVehicle={openVehicle} onOpenDriver={openDriver} onAction={(path: string, label: string) => mutate(() => api.post(path), label)} onSaveSettings={(values: RecordValue) => mutate(() => api.put('/settings', values), 'Workspace preferences saved.')} />}
      </section>
    </main>
    {modal && <Modal title={{ vehicle: 'Add vehicle', driver: 'Add driver', trip: 'Create draft trip', maintenance: 'Log maintenance', fuel: 'Log fuel', expense: 'Add expense' }[modal]} onClose={() => setModal(null)}>
      <EntryForm kind={modal} vehicles={vehicles} drivers={drivers} onSave={async (payload) => {
        const route = { vehicle: '/vehicles', driver: '/drivers', trip: '/trips', maintenance: '/maintenance', fuel: '/finance/fuel', expense: '/finance/expenses' }[modal]
        return mutate(async () => {
          const result = await api.post(route, payload)
          if (modal === 'vehicle') setVehicles((current) => [...current.filter((vehicle) => vehicle.id !== result.data.id), result.data].sort((left, right) => String(left.name).localeCompare(String(right.name))))
          return result
        }, `${modal === 'trip' ? 'Draft trip' : modal[0].toUpperCase() + modal.slice(1)} saved successfully.`)
      }}/>
    </Modal>}
    {vehicleDetail && <VehicleDrawer vehicle={vehicleDetail} onClose={() => setVehicleDetail(null)} onSave={saveVehicle} onRenew={renewDocument} onStart={() => mutate(() => api.post('/maintenance', { vehicle_id: vehicleDetail.id, service_type: 'Workshop intake', cost: 0, notes: 'Started from vehicle profile', status: 'In Progress' }), `${vehicleDetail.name} is now In Shop.`).then(() => openVehicle(vehicleDetail.id))} onAction={(path: string, label: string) => mutate(() => api.post(path), label).then(() => openVehicle(vehicleDetail.id))}/>}
    {driverDetail && <DriverDrawer driver={driverDetail} onClose={() => setDriverDetail(null)}/>}
  </div>
}

function Login({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState('dispatcher@transitops.demo'); const [password, setPassword] = useState('demo'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => { event.preventDefault(); setBusy(true); setError(''); try { await onLogin(email, password) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in.') } finally { setBusy(false) } }
  const chooseFleetDemo = () => { setEmail('fleet@transitops.demo'); setPassword('demo'); setError('') }
  return <div className="login-page"><div className="login-intro"><div className="brand"><span className="brand-mark"><ArrowUpRight size={21}/></span><span>Transit<span>Ops</span></span></div><div><p className="eyebrow">SMART TRANSPORT OPERATIONS</p><h1>Run every trip<br/>with confidence.</h1><p>One calm command centre for fleet availability, driver compliance, live tracking and operating costs.</p></div><section className="fleet-login-spotlight"><img src="/images/fleet/fleet-operations.jpg" alt="TransitOps fleet at a distribution depot"/><div><p>FLEET MANAGER DEMO</p><h3>See availability, compliance and vehicle profiles in one place.</h3><button type="button" onClick={chooseFleetDemo}>Use Fleet Manager demo <ChevronRight size={16}/></button></div></section><div className="login-note"><ShieldCheck size={21}/><span>Server-authorized dispatch and live tracking protect drivers, vehicles, and trip data.</span></div></div><div className="login-panel"><form onSubmit={submit}><p className="eyebrow">WELCOME BACK</p><h2>Sign in to TransitOps</h2><p className="muted">Use a seeded demo account to explore the operational workflow.</p>{error && <div className="form-error">{error}</div>}<label>Work email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></label><label>Password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required /></label><button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <ChevronRight size={18}/></button><div className="demo-users"><p>QUICK DEMO ROLES</p>{[['fleet@transitops.demo', 'Fleet Manager'], ['safety@transitops.demo', 'Safety Officer'], ['driver@transitops.demo', 'Driver'], ['finance@transitops.demo', 'Financial Analyst']].map(([value, label]) => <button type="button" key={value} onClick={() => { setEmail(value); setPassword('demo'); setError('') }}>{label}<span>{value}</span></button>)}</div></form></div></div>
}

function Page(props: RecordValue) {
  const { page } = props
  if (page === 'Dashboard') return <Dashboard {...props}/>
  if (page === 'Fleet') return <Fleet {...props}/>
  if (page === 'Drivers') return <Drivers {...props}/>
  if (page === 'Trips') return <Trips {...props}/>
  if (page === 'Fleet Tracking') return <React.Suspense fallback={<div className="loading">Loading fleet map…</div>}><FleetTrackingPage onNavigate={props.onNavigate}/></React.Suspense>
  if (page === 'My Live Trip') return <React.Suspense fallback={<div className="loading">Loading live trip…</div>}><DriverLiveTripPage/></React.Suspense>
  if (page === 'Maintenance') return <Maintenance {...props}/>
  if (page === 'Fuel & Expenses') return <Finance {...props}/>
  if (page === 'Analytics') return <Analytics {...props}/>
  return <SettingsPage {...props}/>
}

function Dashboard({ dashboard, user, onNavigate }: RecordValue) {
  const [report, setReport] = useState<RecordValue>(dashboard || {})
  const [region, setRegion] = useState(dashboard?.scope?.region || '')
  const [vehicleType, setVehicleType] = useState('')
  const [filterError, setFilterError] = useState('')
  const applyScope = async (clear = false) => {
    const nextRegion = clear ? '' : region; const nextType = clear ? '' : vehicleType
    if (clear) { setRegion(''); setVehicleType('') }
    try { setFilterError(''); setReport((await api.get('/dashboard', { params: Object.fromEntries(Object.entries({ region: nextRegion, vehicle_type: nextType }).filter(([, value]) => value)) })).data) }
    catch (reason) { setFilterError(messageFrom(reason)) }
  }
  const roleQuestions: Record<string, string> = {
    'Fleet Manager': 'Is the fleet healthy, available, compliant, and being used economically?',
    Dispatcher: 'What needs to move now, and what is at risk of delay?',
    'Safety Officer': 'Which driver, vehicle, licence, inspection, or incident presents the greatest safety risk?',
    'Financial Analyst': 'Where is money being spent, and which operations are profitable?',
    Administrator: 'Is the platform secure, configured correctly, and functioning reliably?',
    Driver: 'What is my assignment, and am I ready to complete it safely?',
  }
  const generated = report?.generated_at ? new Date(report.generated_at).toLocaleTimeString() : 'Unavailable'
  const tasks = report?.tasks || []
  const targetForRole: Record<string, string> = { 'Fleet Manager': 'Fleet', Dispatcher: 'Trips', 'Safety Officer': 'Drivers', 'Financial Analyst': 'Analytics', Administrator: 'Settings', Driver: 'My Live Trip' }
  return <div className="role-dashboard"><section className="page-header"><div><p className="eyebrow">{report?.role || user.role} WORKSPACE</p><h1>{roleQuestions[report?.role || user.role]}</h1><p className="muted">Updated {generated}{report?.scope?.region ? ` · ${report.scope.region}` : ''}{report?.scope?.vehicle_type ? ` · ${report.scope.vehicle_type}` : ''}</p></div><button className="primary" onClick={() => onNavigate(targetForRole[user.role])}>Open primary workspace</button></section><section className="analytics-filter panel" aria-label="Dashboard scope"><label>Region<select value={region} onChange={(event) => setRegion(event.target.value)}><option value="">All permitted regions</option>{(report?.filter_options?.regions || []).map((value: string) => <option key={value}>{value}</option>)}</select></label><label>Vehicle type<select value={vehicleType} onChange={(event) => setVehicleType(event.target.value)}><option value="">All vehicle types</option>{(report?.filter_options?.vehicle_types || []).map((value: string) => <option key={value}>{value}</option>)}</select></label><button className="primary" onClick={() => applyScope()}>Apply scope</button><button className="secondary" onClick={() => applyScope(true)}>Clear filters</button></section>{filterError && <div className="form-error">{filterError}</div>}<section className="kpi-grid role-kpis">{(report?.kpis || []).map((kpi: RecordValue, index: number) => <button className={`kpi-card dashboard-kpi kpi-${kpi.status}`} key={kpi.key} onClick={() => kpi.target && onNavigate(kpi.target)} disabled={!kpi.target}><span className={`kpi-icon tone-${index % 4}`}><BarChart3 size={19}/></span><div><p>{kpi.label}</p><h2>{typeof kpi.value === 'number' && kpi.key.includes('cost') ? currency(kpi.value) : kpi.value}</h2><small>{kpi.target ? `Open ${kpi.target}` : 'Current scoped value'}</small></div></button>)}</section><section className="dashboard-grid role-dashboard-grid"><article className="panel action-center"><div className="panel-heading"><div><h3>Action Center</h3><p>Priority work for your role</p></div><Bell size={18}/></div>{tasks.length ? <div className="action-list">{tasks.map((task: RecordValue, index: number) => <button key={`${task.kind}-${index}`} className={`action-item action-${task.severity}`} onClick={() => task.target && onNavigate(task.target)}><AlertTriangle size={16}/><span><b>{task.title}</b><small>{task.kind}</small></span><ChevronRight size={16}/></button>)}</div> : <div className="no-alerts"><CheckCircle2 size={18}/> No priority actions require attention.</div>}</article><article className="panel"><div className="panel-heading"><div><h3>Available modules</h3><p>Generated from backend permissions</p></div><ShieldCheck size={18}/></div><div className="permission-chips">{(report?.permissions || []).map((permission: string) => <span key={permission}>{permission}</span>)}</div></article></section></div>
}

function Fleet({ vehicles, onAdd, onOpenVehicle }: RecordValue) {
  const [query, setQuery] = useState(''); const [status, setStatus] = useState('All'); const [type, setType] = useState('All')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ Available: true, 'On Trip': true, 'In Shop': true, Retired: true })
  const rows: RecordValue[] = vehicles.filter((v: RecordValue) => (status === 'All' || v.status === status) && (type === 'All' || v.vehicle_type === type) && `${v.name} ${v.registration}`.toLowerCase().includes(query.toLowerCase()))
  const states = ['Available', 'On Trip', 'In Shop', 'Retired']
  return <><Header eyebrow="FLEET REGISTRY" title="Fleet and vehicle health" description="Browse availability by state and type, with every profile one click away." action="Add vehicle" onAction={() => onAdd('vehicle')}/><section className="fleet-overview" aria-label="Fleet status summary">{states.map((state) => <button key={state} className={status === state ? 'selected' : ''} onClick={() => setStatus(status === state ? 'All' : state)}><span className={statusClass(state)}>{state}</span><b>{vehicles.filter((vehicle: RecordValue) => vehicle.status === state).length}</b><small>vehicles</small></button>)}</section><FilterBar query={query} onQuery={setQuery} queryLabel="Search registration or vehicle" filters={[{ value: status, onChange: setStatus, options: ['All','Available','On Trip','In Shop','Retired'] }, { value: type, onChange: setType, options: ['All', ...Array.from(new Set<string>(vehicles.map((v: RecordValue) => String(v.vehicle_type))))] } ]}/><div className="fleet-groups">{states.map((state) => { const byState: RecordValue[] = rows.filter((vehicle) => vehicle.status === state); const byType: string[] = Array.from(new Set(byState.map((vehicle) => String(vehicle.vehicle_type)))); return <section className={`fleet-group fleet-${state.toLowerCase().replaceAll(' ', '-')}`} key={state}><button className="fleet-group-heading" onClick={() => setExpanded({ ...expanded, [state]: !expanded[state] })}><span><span className={statusClass(state)}>{state}</span><b>{byState.length}</b></span><ChevronDown size={18} className={expanded[state] ? '' : 'collapsed'}/></button>{expanded[state] && <div className="vehicle-type-groups">{byType.map((vehicleType) => <div className="vehicle-type-group" key={vehicleType}><p>{vehicleType}<span>{byState.filter((vehicle) => vehicle.vehicle_type === vehicleType).length}</span></p><div className="vehicle-card-grid">{byState.filter((vehicle) => vehicle.vehicle_type === vehicleType).map((vehicle) => <button className="vehicle-card" key={vehicle.id} onClick={() => onOpenVehicle(vehicle.id)}><VehicleVisual vehicle={vehicle}/><div className="vehicle-card-main"><div><span className={statusClass(vehicle.status)}>{vehicle.status}</span><h3>{vehicle.name}</h3><b>{vehicle.registration}</b></div><dl><div><dt>Capacity</dt><dd>{vehicle.capacity_kg.toLocaleString()} kg</dd></div><div><dt>Odometer</dt><dd>{vehicle.odometer_km.toLocaleString()} km</dd></div><div><dt>Region</dt><dd><MapPin size={12}/>{vehicle.region}</dd></div></dl></div><span className="card-open" aria-hidden="true"><ChevronRight size={18}/></span></button>)}</div></div>)}{!byState.length && <p className="fleet-empty">No vehicles match these filters.</p>}</div>}</section>})}</div></>
}
function VehicleVisual({ vehicle, large = false }: { vehicle: RecordValue; large?: boolean }) {
  const type = String(vehicle.vehicle_type || '').toLowerCase()
  const photo = vehicle.photo_url || '/images/fleet/fleet-operations.jpg'
  return <div className={`vehicle-visual ${large ? 'vehicle-visual-large' : ''} vehicle-visual-${type.includes('truck') ? 'truck' : type.includes('van') ? 'van' : 'mini'}`}><img src={photo} alt={`${vehicle.name} vehicle`} /></div>
}

function AlertPanel({ alerts, onOpenVehicle }: { alerts: RecordValue[]; onOpenVehicle: (id: string) => void }) {
  return <section className="alert-panel"><div className="alert-panel-heading"><div><p>COMPLIANCE ALERTS</p><h3>Stay ahead of risk</h3></div><Bell size={18}/></div>{alerts.length ? <div className="alert-list">{alerts.map((alert, index) => <button className={`alert-row alert-${alert.severity}`} key={`${alert.entity_id}-${index}`} onClick={() => alert.entity_type === 'vehicle' || alert.entity_type === 'maintenance' ? onOpenVehicle(alert.link.split('/').pop() || '') : undefined}><AlertTriangle size={16}/><span>{alert.message}</span></button>)}</div> : <div className="no-alerts"><CheckCircle2 size={18}/> No active fleet safety alerts.</div>}</section>
}

function VehicleDrawer({ vehicle, onClose, onSave, onRenew, onStart, onAction }: { vehicle: RecordValue; onClose: () => void; onSave: (id: string, payload: RecordValue) => void; onRenew: (document: RecordValue) => void; onStart: () => void; onAction: (path: string, label: string) => void }) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState<RecordValue>(vehicle)
  useEffect(() => setDraft(vehicle), [vehicle])
  const update = (key: string, value: string | number | null) => setDraft((current) => ({ ...current, [key]: value }))
  const addPhoto = (file?: File) => { if (!file) return; const reader = new FileReader(); reader.onload = () => update('photo_url', String(reader.result)); reader.readAsDataURL(file) }
  const save = () => { const numeric = ['capacity_kg', 'odometer_km', 'acquisition_cost', 'manufacture_year']; const payload = Object.fromEntries(Object.entries(draft).filter(([key]) => !['id', 'operational', 'odometer_history', 'documents', 'maintenance_history', 'cost_summary'].includes(key)).map(([key, value]) => [key, numeric.includes(key) && value !== '' && value !== null ? Number(value) : value])); onSave(vehicle.id, payload); setEditing(false) }
  const operational = vehicle.operational || {}; const costs = vehicle.cost_summary || {}
  const maintenanceStatuses = ['In Progress', 'Scheduled', 'Completed', 'Cancelled']
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="vehicle-drawer" onMouseDown={(event) => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Close vehicle profile"><X/></button><div className="vehicle-profile-header"><VehicleVisual vehicle={editing ? draft : vehicle} large/><div><span className={statusClass(vehicle.status)}>{vehicle.status}</span><h2>{vehicle.name}</h2><p>{vehicle.registration}</p></div></div><div className="drawer-actions"><button className="small-secondary" onClick={() => setEditing(!editing)}><Pencil size={15}/>{editing ? 'Cancel edit' : 'Edit'}</button>{vehicle.status !== 'Retired' && <button className="small-secondary" onClick={() => { if (window.confirm(`Retire ${vehicle.name}?`)) onAction(`/vehicles/${vehicle.id}/retire`, `${vehicle.name} retired.`) }}><Ban size={15}/>Retire</button>}{vehicle.status === 'Available' && <button className="small-primary" onClick={onStart}><Play size={15}/>Start maintenance</button>}</div>{editing && <section className="drawer-section edit-section"><div className="section-heading"><Pencil size={17}/><h3>Edit vehicle</h3></div><div className="vehicle-edit-grid">{[['name','Name'],['registration','Registration'],['vehicle_type','Type'],['brand','Brand'],['model','Model'],['vin','VIN'],['fuel_type','Fuel type'],['manufacture_year','Manufacture year'],['color','Color'],['capacity_kg','Capacity (kg)'],['odometer_km','Odometer (km)'],['acquisition_cost','Acquisition cost'],['region','Region']].map(([key,label]) => <label key={key}>{label}{key === 'fuel_type' ? <select value={draft[key] || 'Diesel'} onChange={(event) => update(key, event.target.value)}>{['Diesel','Petrol','CNG','Electric','Hybrid'].map((type) => <option key={type}>{type}</option>)}</select> : <input value={draft[key] ?? ''} onChange={(event) => update(key, event.target.value)} type={['capacity_kg','odometer_km','acquisition_cost','manufacture_year'].includes(key) ? 'number' : 'text'}/>}</label>)}<label className="photo-field">Vehicle photo<input type="file" accept="image/*" onChange={(event) => addPhoto(event.target.files?.[0])}/><span><Camera size={14}/> Upload or replace image</span></label></div><button className="primary full" onClick={save}>Save vehicle profile</button></section>}<section className="drawer-section"><div className="section-heading"><ClipboardCheck size={17}/><h3>Specifications</h3></div><div className="spec-grid">{[['Brand',vehicle.brand || '—'],['Model',vehicle.model || '—'],['VIN',vehicle.vin || '—'],['Fuel type',vehicle.fuel_type],['Manufacture year',vehicle.manufacture_year || '—'],['Colour',vehicle.color || '—'],['Type',vehicle.vehicle_type],['Capacity',`${vehicle.capacity_kg.toLocaleString()} kg`],['Acquisition cost',currency(vehicle.acquisition_cost)],['Region',vehicle.region]].map(([label,value]) => <div key={label}><span>{label}</span><b>{value}</b></div>)}</div></section><section className="drawer-section"><div className="section-heading"><Gauge size={17}/><h3>Operational status</h3></div><div className="operational-card"><div><span>Current odometer</span><b>{vehicle.odometer_km.toLocaleString()} km</b></div><div><span>Assigned driver</span><b>{operational.assigned_driver?.name || 'Unassigned'}</b></div>{operational.current_trip && <div className="current-trip"><span>Current trip</span><b>{operational.current_trip.source} <ChevronRight size={13}/> {operational.current_trip.destination}</b><small>{operational.current_trip.cargo_kg.toLocaleString()} kg · {operational.current_trip.status}</small></div>}</div></section><section className="drawer-section"><div className="section-heading"><Gauge size={17}/><h3>Odometer history</h3></div><div className="timeline">{(vehicle.odometer_history || []).map((log: RecordValue) => <div className="timeline-row" key={log.id}><i/><div><b>{log.value_km.toLocaleString()} km</b><span>{log.source}{log.driver ? ` · ${log.driver}` : ''}</span></div><small>{log.date}</small></div>)}{!vehicle.odometer_history?.length && <p className="muted">No readings recorded yet.</p>}</div></section><section className="drawer-section"><div className="section-heading"><FileText size={17}/><h3>Documents & compliance</h3></div><div className="document-list">{(vehicle.documents || []).map((document: RecordValue) => <div className="document-row" key={document.id}><div><b>{document.document_type}</b><span>{document.reference_number || 'No reference'} · {document.provider || 'No provider'}</span><small>{document.start_date} — {document.expiry_date} · {currency(document.cost)}</small></div><span className={statusClass(document.status)}>{document.status}</span>{document.status !== 'Renewed' && <button className="text-button" onClick={() => onRenew(document)}>Renew</button>}</div>)}</div></section><section className="drawer-section"><div className="section-heading"><Wrench size={17}/><h3>Maintenance history</h3></div>{maintenanceStatuses.map((status) => { const records = (vehicle.maintenance_history || []).filter((record: RecordValue) => record.status === status); return records.length ? <div className="maintenance-history-group" key={status}><p><span className={statusClass(status)}>{status}</span>{records.length}</p>{records.map((record: RecordValue) => <div className="maintenance-history-row" key={record.id}><div><b>{record.service_type}</b><span>{record.vendor || 'No vendor'} · {record.invoice_reference || 'No invoice'}</span></div><small>{currency(record.cost)} · {record.downtime_days} day{record.downtime_days === 1 ? '' : 's'}</small></div>)}</div> : null })}</section><section className="drawer-section cost-summary"><div><span>Fuel</span><b>{currency(costs.fuel || 0)}</b></div><div><span>Maintenance</span><b>{currency(costs.maintenance || 0)}</b></div><div><span>Documents</span><b>{currency(costs.documents || 0)}</b></div><div><span>Total cost</span><b>{currency(costs.total || 0)}</b></div></section></aside></div>
}
function Drivers({ drivers, onAdd, onOpenDriver }: RecordValue) {
  const [query, setQuery] = useState(''); const [status, setStatus] = useState('All')
  const rows = drivers.filter((d: RecordValue) => (status === 'All' || d.status === status) && `${d.name} ${d.license_number}`.toLowerCase().includes(query.toLowerCase()))
  return <><Header eyebrow="DRIVER DIRECTORY" title="Compliance and availability" description="Open a driver profile to review licence, safety and current assignment context." action="Add driver" onAction={() => onAdd('driver')}/><FilterBar query={query} onQuery={setQuery} queryLabel="Search name or licence" filters={[{ value: status, onChange: setStatus, options: ['All','Available','On Trip','Off Duty','Suspended'] }]}/><div className="driver-card-grid">{rows.map((driver: RecordValue) => <button className="driver-card" key={driver.id} onClick={() => onOpenDriver(driver)}><DriverAvatar driver={driver}/><div className="driver-card-content"><div className="driver-card-heading"><div><span className={statusClass(driver.status)}>{driver.status}</span><h3>{driver.name}</h3><p>{driver.license_category} · {driver.region}</p></div><ChevronRight size={18}/></div><div className="driver-card-metrics"><span><Star size={14}/>{driver.safety_score}% safety</span><span><UserRound size={14}/>{driver.status === 'On Trip' ? 'Active assignment' : 'No active assignment'}</span></div><small>Licence {driver.license_number} · expires {driver.license_expiry}</small></div></button>)}</div>{!rows.length && <p className="fleet-empty">No drivers match these filters.</p>}</>
}

function DriverAvatar({ driver, large = false }: { driver: RecordValue; large?: boolean }) {
  const initials = String(driver.name || '?').split(' ').map((part) => part[0]).join('').slice(0, 2)
  return <div className={`driver-avatar-photo ${large ? 'driver-avatar-large' : ''}`}>{driver.photo_url ? <img src={driver.photo_url} alt={`${driver.name} profile`} /> : <span>{initials}</span>}</div>
}

function DriverDrawer({ driver, onClose }: { driver: RecordValue; onClose: () => void }) {
  const expiry = new Date(`${driver.license_expiry}T00:00:00`)
  const licenceState = expiry < new Date() ? 'Expired' : expiry < new Date(Date.now() + 1000 * 60 * 60 * 24 * 90) ? 'Review soon' : 'Current'
  const assignment = driver.status === 'On Trip' ? 'Active trip in progress' : driver.status === 'Available' ? 'Ready for dispatch' : 'Not currently assigned'
  return <div className="drawer-backdrop" onMouseDown={onClose}><aside className="vehicle-drawer driver-drawer" onMouseDown={(event) => event.stopPropagation()}><button className="drawer-close" onClick={onClose} aria-label="Close driver profile"><X/></button><div className="driver-profile-header"><DriverAvatar driver={driver} large/><div><span className={statusClass(driver.status)}>{driver.status}</span><h2>{driver.name}</h2><p>{driver.license_category} licence · {driver.region}</p></div></div><section className="drawer-section driver-score"><div><span>Safety rating</span><b>{driver.safety_score}%</b><small>Based on demo compliance performance</small></div><Star size={28}/></section><section className="drawer-section"><div className="section-heading"><UserRound size={17}/><h3>Driver profile</h3></div><div className="spec-grid"><div><span>Licence</span><b>{driver.license_number}</b></div><div><span>Licence state</span><b>{licenceState}</b></div><div><span>Depot</span><b>{driver.depot}</b></div><div><span>Assignment</span><b>{assignment}</b></div></div></section><section className="drawer-section"><div className="section-heading"><Phone size={17}/><h3>Contact</h3></div><a className="driver-contact" href={`tel:${String(driver.contact).replaceAll(' ', '')}`}><Phone size={16}/>{driver.contact}</a></section><section className="drawer-section driver-safety-note"><div className="section-heading"><ShieldCheck size={17}/><h3>Safety context</h3></div><p>{driver.safety_score >= 90 ? 'Strong safety record. Continue routine licence and trip-readiness checks.' : driver.safety_score >= 80 ? 'Good safety record. Review recent trip notes during the next check-in.' : 'Safety follow-up is recommended before assigning a new trip.'}</p></section></aside></div>
}
function Trips({ trips, user, onAdd, onAction }: RecordValue) { const states = ['Draft', 'Dispatched', 'In Progress', 'Completed', 'Cancelled']; const canDispatch = ['Fleet Manager', 'Dispatcher', 'Administrator'].includes(user.role); return <><Header eyebrow={canDispatch ? 'TRIP DISPATCHER' : 'TRIP SAFETY VIEW'} title={canDispatch ? 'Plan, dispatch, track, and complete' : 'Review active trips and driver safety context'} description="Availability, cargo capacity, and active tracking assignments are enforced by the server." action={canDispatch ? 'New trip' : undefined} onAction={() => onAdd('trip')}/><div className="workflow-note"><ShieldCheck size={18}/><span>Protected workflow: tracking can start after dispatch and stops automatically on completion or cancellation.</span></div><div className="trip-board five-columns">{states.map((state) => <section className="board-column" key={state}><div className="board-title"><span>{state}</span><b>{trips.filter((t: RecordValue) => t.status === state).length}</b></div>{trips.filter((t: RecordValue) => t.status === state).map((trip: RecordValue) => <article className="trip-card" key={trip.id}><div><b>{trip.id}</b><span className={statusClass(trip.status)}>{trip.status}</span></div><h4>{trip.source} <ChevronRight size={15}/> {trip.destination}</h4><p>{trip.vehicle} · {trip.driver}</p><small>{trip.cargo_kg.toLocaleString()} kg · {trip.planned_distance_km} km</small>{canDispatch && state === 'Draft' && <button className="small-primary" onClick={() => onAction(`/trips/${trip.id}/dispatch`, `${trip.id} dispatched. Vehicle and driver are now On Trip.`)}>Dispatch</button>}{canDispatch && (state === 'Dispatched' || state === 'In Progress') && <div className="card-actions"><button className="small-primary" onClick={() => onAction(`/trips/${trip.id}/complete`, `${trip.id} completed; tracking stopped and resources released.`)}>Complete</button><button className="small-secondary" onClick={() => onAction(`/trips/${trip.id}/cancel`, `${trip.id} cancelled; tracking stopped and resources released.`)}>Cancel</button></div>}</article>)}</section>)}</div></> }
function Maintenance({ maintenance, onAdd, onAction }: RecordValue) { return <><Header eyebrow="MAINTENANCE" title="Protect fleet availability" description="Scheduled work preserves availability; only In Progress work moves a vehicle to In Shop." action="Schedule maintenance" onAction={() => onAdd('maintenance')}/><Table columns={['Vehicle', 'Service', 'Vendor', 'Priority', 'Due', 'Status', 'Action']} rows={maintenance.map((m: RecordValue) => [<b>{m.vehicle}</b>, m.service_type, m.vendor || '—', <span className={m.priority === 'Urgent' ? 'priority-urgent' : ''}>{m.priority}</span>, m.due_date || '—', <span className={statusClass(m.status)}>{m.status}</span>, m.status === 'Scheduled' ? <div className="card-actions"><button className="small-primary" onClick={() => onAction(`/maintenance/${m.id}/start`, `${m.vehicle} is now In Shop.`)}>Start</button><button className="small-secondary" onClick={() => onAction(`/maintenance/${m.id}/cancel`, 'Maintenance cancelled.')}>Cancel</button></div> : m.status === 'In Progress' ? <div className="card-actions"><button className="small-primary" onClick={() => onAction(`/maintenance/${m.id}/close`, `${m.vehicle} is available again.`)}>Complete</button><button className="small-secondary" onClick={() => onAction(`/maintenance/${m.id}/cancel`, 'Maintenance cancelled.')}>Cancel</button></div> : <span className="muted">{m.closed_at ? `Closed ${m.closed_at}` : '—'}</span>])}/></> }
function Finance({ finance, onAdd }: RecordValue) { return <><Header eyebrow="FUEL & EXPENSES" title="Operating cost, without guesswork" description="Operational cost consistently includes fuel, maintenance, tolls, and miscellaneous expenses." action="Log fuel" onAction={() => onAdd('fuel')} secondary="Add expense" onSecondary={() => onAdd('expense')}/><section className="cost-strip"><div><span>Operational cost</span><b>{currency(finance?.operationalCost || 0)}</b><small>Fuel + maintenance + other expenses</small></div><div><span>Recorded expenses</span><b>{currency(finance?.expandedCost || 0)}</b><small>Same committed cost definition</small></div></section><div className="two-tables"><Table title="Fuel logs" columns={['Vehicle', 'Date', 'Litres', 'Rate', 'Cost', 'Vendor', 'Receipt']} rows={(finance?.fuelLogs || []).map((f: RecordValue) => [f.vehicle, f.date, `${f.liters} L`, f.price_per_liter ? currency(f.price_per_liter) : '-', currency(f.cost), f.vendor || '-', f.receipt_image ? <a href={String(api.defaults.baseURL).replace(/\/api$/, '') + f.receipt_image} target="_blank" rel="noreferrer">View</a> : '-'])}/><Table title="Other expenses" columns={['Category', 'Vehicle', 'Date', 'Amount', 'Notes']} rows={(finance?.expenses || []).map((e: RecordValue) => [e.category, e.vehicle, e.date, currency(e.amount), e.notes || '-'])}/></div></> }
function Analytics({ analytics }: RecordValue) {
  const [report, setReport] = useState<RecordValue>(analytics || {})
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [vehicleId, setVehicleId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const params = () => Object.fromEntries(Object.entries({ date_from: dateFrom, date_to: dateTo, vehicle_id: vehicleId }).filter(([, value]) => value))
  const applyFilters = async () => {
    setBusy(true); setError('')
    try { setReport((await api.get('/analytics', { params: params() })).data) }
    catch (reason) { setError(messageFrom(reason)) }
    finally { setBusy(false) }
  }
  const download = async () => {
    try {
      const response = await api.get('/analytics/export', { params: params(), responseType: 'blob' })
      const link = document.createElement('a'); link.href = URL.createObjectURL(response.data); link.download = 'transitops-analytics.csv'; link.click(); URL.revokeObjectURL(link.href)
    } catch (reason) { setError(messageFrom(reason)) }
  }
  const metrics = report?.metrics || {}
  const ranking = report?.costliestVehicles || []
  const maxCost = Math.max(1, ...ranking.map((item: RecordValue) => item.cost))
  return <><Header eyebrow="REPORTS & ANALYTICS" title="Fleet performance, explained" description="Filters, KPIs, charts, and CSV export use the same committed records and cost definition."/><section className="analytics-filter panel"><label>From<input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)}/></label><label>To<input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)}/></label><label>Vehicle<select value={vehicleId} onChange={(event) => setVehicleId(event.target.value)}><option value="">All vehicles</option>{(report?.filterOptions?.vehicles || []).map((vehicle: RecordValue) => <option value={vehicle.id} key={vehicle.id}>{vehicle.name}</option>)}</select></label><button className="primary" onClick={applyFilters} disabled={busy}>{busy ? 'Applying…' : 'Apply filters'}</button><button className="secondary" onClick={download}><Download size={17}/> Export current view</button></section>{error && <div className="form-error">{error}</div>}<section className="kpi-grid analytics-cards">{[['Fuel efficiency', metrics.fuelEfficiency ? `${metrics.fuelEfficiency} km/L` : 'N/A'], ['Fleet utilization', `${metrics.utilization || 0}%`], ['Operational cost', currency(metrics.operationalCost || 0)], ['Vehicle ROI', metrics.roi === null ? 'N/A' : `${metrics.roi}%`]].map(([label, value], index) => <article className="metric-card" key={label}><span>{label}</span><b className={`metric-${index}`}>{value}</b></article>)}</section><section className="dashboard-grid"><article className="panel"><div className="panel-heading"><div><h3>Monthly revenue</h3><p>Completed-trip revenue for the selected scope</p></div></div><div className="bar-chart"><ResponsiveContainer width="100%" height={260}><BarChart data={report?.revenue || []}><CartesianGrid vertical={false} stroke="#e8edf4"/><XAxis dataKey="month" axisLine={false} tickLine={false}/><YAxis hide/><Tooltip formatter={(value) => currency(Number(value))}/><Bar dataKey="amount" fill="#2f7aef" radius={[6,6,0,0]}/></BarChart></ResponsiveContainer></div></article><article className="panel"><div className="panel-heading"><div><h3>Costliest vehicles</h3><p>Fuel + maintenance + other vehicle expenses</p></div></div><div className="cost-ranking">{ranking.map((item: RecordValue, index: number) => <div key={item.vehicle}><div><span>{index + 1}</span><b>{item.vehicle}</b><strong>{currency(item.cost)}</strong></div><i><em style={{ width: `${Math.max(8, item.cost / maxCost * 100)}%` }}/></i></div>)}</div></article></section></>
}
function SettingsPage({ user, preferences, permissionSummary, onSaveSettings }: RecordValue) {
  const [values, setValues] = useState<RecordValue>(preferences || { depot_name: '', currency: 'INR', distance_unit: 'Kilometres' })
  useEffect(() => setValues(preferences || { depot_name: '', currency: 'INR', distance_unit: 'Kilometres' }), [preferences])
  const set = (key: string, value: unknown) => setValues((current: RecordValue) => ({ ...current, [key]: value }))
  return <><Header eyebrow="SETTINGS & RBAC" title="Workspace and tracking preferences" description="Live-location policy and role permissions are enforced by the API."/><form className="settings-form" onSubmit={(event) => { event.preventDefault(); onSaveSettings(values) }}><section className="settings-grid"><article className="panel preference-card"><h3>General</h3><label>Depot name<input value={values.depot_name || ''} onChange={(event) => set('depot_name', event.target.value)} required/></label><label>Currency<select value={values.currency || 'INR'} onChange={(event) => set('currency', event.target.value)}><option value="INR">INR</option><option value="USD">USD</option></select></label><label>Distance unit<select value={values.distance_unit || 'Kilometres'} onChange={(event) => set('distance_unit', event.target.value)}><option>Kilometres</option><option>Miles</option></select></label><label className="setting-toggle"><input type="checkbox" checked={values.live_tracking_enabled ?? true} onChange={(event) => set('live_tracking_enabled', event.target.checked)}/><span>Enable live tracking</span></label><label>Map provider<select value={values.map_provider || 'openstreetmap'} onChange={(event) => set('map_provider', event.target.value)}><option value="openstreetmap">OpenStreetMap</option><option value="mapbox">Mapbox</option><option value="google">Google Maps</option></select></label><label>Directions provider<select value={values.directions_provider || 'straight_line'} onChange={(event) => set('directions_provider', event.target.value)}><option value="straight_line">Straight-line estimate</option><option value="openrouteservice">OpenRouteService</option><option value="mapbox">Mapbox</option><option value="google">Google Maps</option></select></label></article><article className="panel tracking-settings-card"><h3>Tracking policy</h3><div className="tracking-setting-grid"><label>Moving interval (seconds)<input type="number" min="5" value={values.tracking_update_interval_seconds ?? 10} onChange={(event) => set('tracking_update_interval_seconds', Number(event.target.value))}/></label><label>Stationary interval (seconds)<input type="number" min="10" value={values.tracking_stationary_interval_seconds ?? 25} onChange={(event) => set('tracking_stationary_interval_seconds', Number(event.target.value))}/></label><label>Minimum movement (metres)<input type="number" min="1" value={values.tracking_minimum_movement_meters ?? 20} onChange={(event) => set('tracking_minimum_movement_meters', Number(event.target.value))}/></label><label>Stale threshold (seconds)<input type="number" min="15" value={values.tracking_stale_seconds ?? 60} onChange={(event) => set('tracking_stale_seconds', Number(event.target.value))}/></label><label>Offline threshold (seconds)<input type="number" min="30" value={values.tracking_offline_seconds ?? 180} onChange={(event) => set('tracking_offline_seconds', Number(event.target.value))}/></label><label>Raw retention (days)<input type="number" min="1" value={values.tracking_raw_retention_days ?? 60} onChange={(event) => set('tracking_raw_retention_days', Number(event.target.value))}/></label><label>Driver fleet visibility<select value={values.driver_fleet_visibility || 'OWN_VEHICLE_ONLY'} onChange={(event) => set('driver_fleet_visibility', event.target.value)}><option>OWN_VEHICLE_ONLY</option><option>SAME_TRIP_GROUP</option><option>SAME_DEPOT_ACTIVE_VEHICLES</option><option>ALL_AUTHORIZED_ACTIVE_VEHICLES</option></select></label><label className="setting-toggle"><input type="checkbox" checked={values.allow_driver_pause ?? true} onChange={(event) => set('allow_driver_pause', event.target.checked)}/><span>Allow driver pause</span></label><label className="setting-toggle"><input type="checkbox" checked={values.allow_driver_nearby_vehicles ?? false} onChange={(event) => set('allow_driver_nearby_vehicles', event.target.checked)}/><span>Allow nearby vehicles</span></label><label className="setting-toggle"><input type="checkbox" checked={values.geofence_alerts_enabled ?? true} onChange={(event) => set('geofence_alerts_enabled', event.target.checked)}/><span>Geofence alerts</span></label></div></article></section><article className="panel settings-rbac"><h3>Effective backend permissions</h3><p className="muted">Signed in as <b>{user.role}</b>. This list comes from the same server policy used to authorize every API request.</p><div className="permission-chips">{(permissionSummary?.permissions || []).map((permission: string) => <span key={permission}><CheckCircle2 size={14}/>{permission}</span>)}</div></article><div className="settings-save-row"><button className="primary">Save tracking settings</button></div></form></> }

function Header({ eyebrow, title, description, action, onAction, secondary, onSecondary, actionIcon }: RecordValue) { return <section className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action && <div className="header-actions">{secondary && <button className="secondary" onClick={onSecondary}><Plus size={17}/>{secondary}</button>}<button className="primary" onClick={onAction}>{actionIcon || <Plus size={18}/>}{action}</button></div>}</section> }
function FilterBar({ query, onQuery, queryLabel, filters }: { query: string; onQuery: (value: string) => void; queryLabel: string; filters: { value: string; onChange: (value: string) => void; options: string[] }[] }) { return <div className="filter-bar"><label><Search size={16}/><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder={queryLabel}/></label>{filters.map((filter, index) => <select key={index} value={filter.value} onChange={(event) => filter.onChange(event.target.value)}>{filter.options.map((option) => <option key={option}>{option}</option>)}</select>)}</div> }
function Table({ title, columns, rows, empty }: { title?: string; columns: string[]; rows: React.ReactNode[][]; empty?: string }) { return <article className="panel table-panel">{title && <div className="panel-heading"><div><h3>{title}</h3></div></div>}<div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>) : <tr><td colSpan={columns.length} className="empty-cell">{empty || 'No records yet.'}</td></tr>}</tbody></table></div></article> }
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop"><div className="modal"><div className="modal-heading"><div><p className="eyebrow">NEW RECORD</p><h2>{title}</h2></div><button onClick={onClose} aria-label="Close"><X/></button></div>{children}</div></div> }
function EntryForm({ kind, vehicles, drivers, onSave }: { kind: string; vehicles: RecordValue[]; drivers: RecordValue[]; onSave: (payload: RecordValue) => Promise<boolean> }) {
  const [payload, setPayload] = useState<RecordValue>(() => ({ status: kind === 'maintenance' ? 'Scheduled' : 'Available', priority: 'Normal', region: 'Ahmedabad', fuel_type: 'Diesel', license_expiry: '2027-12-31', safety_score: 90, vehicle_id: vehicles.find((v) => v.status === 'Available')?.id || '', driver_id: drivers.find((d) => d.status === 'Available')?.id || '', category: 'Toll' }))
  const [saving, setSaving] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const set = (key: string, value: string) => setPayload((current) => ({ ...current, [key]: value }))
  if (kind === 'fuel') return <FuelEntryForm api={api} vehicles={vehicles} onSave={onSave}/>
/* Superseded entry-form variant retained below only during conflict resolution.
  const fields: Record<string, [string, string, string?][]> = { vehicle: [['registration','Registration','text'],['name','Vehicle name','text'],['vehicle_type','Type','text'],['capacity_kg','Capacity (kg)','number'],['odometer_km','Odometer (km)','number'],['acquisition_cost','Acquisition cost','number'],['region','Region','text']], driver: [['name','Full name','text'],['license_number','Licence number','text'],['license_category','Licence category','text'],['license_expiry','Licence expiry','date'],['contact','Contact','tel'],['safety_score','Safety score','number'],['region','Region','text']], trip: [['source','Source','text'],['destination','Destination','text'],['source_latitude','Source latitude','number'],['source_longitude','Source longitude','number'],['destination_latitude','Destination latitude','number'],['destination_longitude','Destination longitude','number'],['cargo_kg','Cargo weight (kg)','number'],['planned_distance_km','Planned distance (km)','number'],['revenue','Expected revenue','number'],['notes','Notes','text']], maintenance: [['service_type','Service type','text'],['cost','Estimated cost','number'],['notes','Notes','text']], fuel: [['liters','Litres','number'],['cost','Total cost','number'],['odometer_km','Odometer (km)','number'],['vendor','Vendor','text']], expense: [['amount','Amount','number'],['notes','Notes','text']] }
  const save = (event: FormEvent) => { event.preventDefault(); const numeric = ['capacity_kg','odometer_km','acquisition_cost','safety_score','cargo_kg','planned_distance_km','revenue','cost','liters','amount','source_latitude','source_longitude','destination_latitude','destination_longitude']; const parsed = Object.fromEntries(Object.entries(payload).filter(([,value]) => value !== '').map(([key,value]) => [key, numeric.includes(key) ? Number(value) : value])); onSave(parsed) }
  return <form className="entry-form" onSubmit={save}>{(kind === 'trip' || kind === 'maintenance' || kind === 'fuel') && <label>Vehicle<select value={payload.vehicle_id} onChange={(event) => set('vehicle_id', event.target.value)} required><option value="">Select vehicle</option>{vehicles.map((vehicle) => <option value={vehicle.id} key={vehicle.id}>{vehicle.name} · {vehicle.status}</option>)}</select></label>}{kind === 'trip' && <label>Driver<select value={payload.driver_id} onChange={(event) => set('driver_id', event.target.value)} required><option value="">Select driver</option>{drivers.map((driver) => <option value={driver.id} key={driver.id}>{driver.name} · {driver.status}</option>)}</select></label>}{kind === 'expense' && <label>Category<select value={payload.category} onChange={(event) => set('category', event.target.value)}><option>Toll</option><option>Miscellaneous</option></select></label>}{fields[kind].map(([key, label, type]) => <label key={key}>{label}<input value={payload[key] ?? ''} onChange={(event) => set(key, event.target.value)} type={type || 'text'} required={['registration','name','vehicle_type','capacity_kg','license_number','source','destination','service_type','liters','cost','amount'].includes(key)}/></label>)}<button className="primary full" type="submit">Save record <ChevronRight size={18}/></button></form>
*/
  const fields: Record<string, [string, string, string?][]> = { vehicle: [['registration','Registration','text'],['name','Vehicle name','text'],['vehicle_type','Type','text'],['brand','Brand','text'],['model','Model','text'],['vin','VIN','text'],['manufacture_year','Manufacture year','number'],['color','Colour','text'],['capacity_kg','Capacity (kg)','number'],['odometer_km','Odometer (km)','number'],['acquisition_cost','Acquisition cost','number'],['region','Region','text']], driver: [['name','Full name','text'],['license_number','Licence number','text'],['license_category','Licence category','text'],['license_expiry','Licence expiry','date'],['contact','Contact','tel'],['safety_score','Safety score','number'],['region','Region','text']], trip: [['source','Source','text'],['destination','Destination','text'],['cargo_kg','Cargo weight (kg)','number'],['planned_distance_km','Planned distance (km)','number'],['revenue','Expected revenue','number'],['notes','Notes','text']], maintenance: [['service_type','Service type','text'],['vendor','Service provider','text'],['invoice_reference','Invoice reference','text'],['odometer_km','Service odometer (optional)','number'],['due_date','Expected completion','date'],['cost','Estimated cost','number'],['notes','Notes','text']], fuel: [['liters','Litres','number'],['cost','Total cost','number'],['odometer_km','Odometer (km)','number'],['vendor','Vendor','text']], expense: [['amount','Amount','number'],['notes','Notes','text']] }
  const upload = (file?: File) => { if (!file) return; const reader = new FileReader(); reader.onload = () => set('photo_url', String(reader.result)); reader.readAsDataURL(file) }
  const save = async (event: FormEvent) => { event.preventDefault(); const numeric = ['capacity_kg','odometer_km','acquisition_cost','manufacture_year','safety_score','cargo_kg','planned_distance_km','revenue','cost','liters','amount']; const parsed = Object.fromEntries(Object.entries(payload).filter(([, value]) => value !== '').map(([key,value]) => [key, numeric.includes(key) ? Number(value) : value])); setSaving(true); setSubmitError(''); const saved = await onSave(parsed); if (!saved) { setSaving(false); setSubmitError('We could not save this record. Review the message above and try again.') } }
  return <form className="entry-form" onSubmit={save}>{(kind === 'trip' || kind === 'maintenance' || kind === 'fuel') && <label>Vehicle<select value={payload.vehicle_id} onChange={(event) => set('vehicle_id', event.target.value)} required><option value="">Select vehicle</option>{vehicles.map((vehicle) => <option value={vehicle.id} key={vehicle.id}>{vehicle.name} · {vehicle.status}</option>)}</select></label>}{kind === 'trip' && <label>Driver<select value={payload.driver_id} onChange={(event) => set('driver_id', event.target.value)} required><option value="">Select driver</option>{drivers.map((driver) => <option value={driver.id} key={driver.id}>{driver.name} · {driver.status}</option>)}</select></label>}{kind === 'vehicle' && <><label>Fuel type<select value={payload.fuel_type} onChange={(event) => set('fuel_type', event.target.value)}>{['Diesel','Petrol','CNG','Electric','Hybrid'].map((value) => <option key={value}>{value}</option>)}</select></label><label className="photo-field">Vehicle photo<input type="file" accept="image/*" onChange={(event) => upload(event.target.files?.[0])}/><span><Camera size={14}/> Upload image</span></label></>}{kind === 'maintenance' && <><label>Priority<select value={payload.priority} onChange={(event) => set('priority', event.target.value)}>{['Low','Normal','Urgent'].map((value) => <option key={value}>{value}</option>)}</select></label><label>Initial state<select value={payload.status} onChange={(event) => set('status', event.target.value)}><option>Scheduled</option><option>In Progress</option></select></label></>}{kind === 'expense' && <label>Category<select value={payload.category} onChange={(event) => set('category', event.target.value)}><option>Toll</option><option>Miscellaneous</option></select></label>}{fields[kind].map(([key, label, type]) => <label key={key}>{label}<input value={payload[key] ?? ''} onChange={(event) => set(key, event.target.value)} type={type || 'text'} required={['registration','name','vehicle_type','capacity_kg','odometer_km','acquisition_cost','license_number','source','destination','service_type','liters','cost','amount'].includes(key)}/></label>)}{submitError && <div className="form-error">{submitError}</div>}<button className="primary full" type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save record'} <ChevronRight size={18}/></button></form>
}
function Loading() { return <div className="loading"><div/><p>Loading operational data…</p></div> }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
