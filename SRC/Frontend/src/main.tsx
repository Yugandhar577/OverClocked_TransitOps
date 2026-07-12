import React, { FormEvent, useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import axios from 'axios'
import {
  BarChart3, CarFront, ChevronRight, CircleDollarSign, ClipboardList, Fuel,
  LayoutDashboard, LogOut, Menu, Plus, Settings, ShieldCheck, Users, Wrench,
  X, CheckCircle2, AlertTriangle, Search, ArrowUpRight, Download
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import './styles.css'
import { FuelEntryForm } from './FuelEntryForm'

type User = { id: string; name: string; email: string; role: string }
type Session = { access_token: string; user: User }
type RecordValue = Record<string, any>

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api' })
api.interceptors.request.use((config) => {
  const session = localStorage.getItem('transitops-session')
  if (session) config.headers.Authorization = `Bearer ${JSON.parse(session).access_token}`
  return config
})

const nav = [
  { key: 'Dashboard', icon: LayoutDashboard, roles: ['Fleet Manager', 'Dispatcher', 'Safety Officer', 'Financial Analyst', 'Administrator'] },
  { key: 'Fleet', icon: CarFront, roles: ['Fleet Manager', 'Administrator'] },
  { key: 'Drivers', icon: Users, roles: ['Fleet Manager', 'Safety Officer', 'Administrator'] },
  { key: 'Trips', icon: ClipboardList, roles: ['Fleet Manager', 'Dispatcher', 'Safety Officer', 'Administrator'] },
  { key: 'Maintenance', icon: Wrench, roles: ['Fleet Manager', 'Administrator'] },
  { key: 'Fuel & Expenses', icon: Fuel, roles: ['Fleet Manager', 'Financial Analyst', 'Administrator'] },
  { key: 'Analytics', icon: BarChart3, roles: ['Fleet Manager', 'Financial Analyst', 'Administrator'] },
  { key: 'Settings', icon: Settings, roles: ['Fleet Manager', 'Administrator'] },
]

const statusClass = (status: string) => `status status-${status.toLowerCase().replaceAll(' ', '-')}`
const currency = (value: number) => new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(value)
const apiOfflineMessage = 'The API is not reachable. Start the FastAPI server on port 8000.'
const messageFrom = (error: unknown, fallback = 'Unable to save this change.') => axios.isAxiosError(error) ? error.response?.data?.detail || fallback : fallback
const isSessionFailure = (error: unknown) => {
  if (!axios.isAxiosError(error)) return false
  const status = error.response?.status
  return status === 401 || (status === 404 && error.response?.data?.detail === 'Record not found.')
}
const readSavedSession = () => {
  const saved = localStorage.getItem('transitops-session')
  if (!saved) return null
  try {
    return JSON.parse(saved) as Session
  } catch {
    localStorage.removeItem('transitops-session')
    return null
  }
}

function App() {
  const [session, setSession] = useState<Session | null>(() => readSavedSession())
  const [page, setPage] = useState('Dashboard')
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
  const [modal, setModal] = useState<'vehicle' | 'driver' | 'trip' | 'maintenance' | 'fuel' | 'expense' | null>(null)

  const allowedNav = useMemo(() => nav.filter((item) => session && item.roles.includes(session.user.role)), [session])

  const load = async () => {
    if (!session) return
    setLoading(true)
    try {
      const canManageSettings = ['Fleet Manager', 'Administrator'].includes(session.user.role)
      const [dash, vehicleData, driverData, tripData, maintenanceData, financeData, analyticsData, settingsData] = await Promise.all([
        api.get('/dashboard'), api.get('/vehicles'), api.get('/drivers'), api.get('/trips'), api.get('/maintenance'), api.get('/finance'), api.get('/analytics'),
        canManageSettings ? api.get('/settings') : Promise.resolve({ data: null }),
      ])
      setDashboard(dash.data); setVehicles(vehicleData.data); setDrivers(driverData.data); setTrips(tripData.data)
      setMaintenance(maintenanceData.data); setFinance(financeData.data); setAnalytics(analyticsData.data); setPreferences(settingsData.data)
    } catch (error) {
      if (isSessionFailure(error)) {
        localStorage.removeItem('transitops-session')
        setSession(null)
        setNotice('')
        return
      }
      setNotice(messageFrom(error, apiOfflineMessage))
    } finally { setLoading(false) }
  }

  useEffect(() => { load() }, [session])

  const login = async (email: string, password: string) => {
    try {
      const result = await api.post('/auth/login', { email, password })
      localStorage.setItem('transitops-session', JSON.stringify(result.data))
      setSession(result.data); setNotice('Signed in to the seeded hackathon workspace.')
    } catch (error) { throw new Error(messageFrom(error, apiOfflineMessage)) }
  }

  const logout = () => { localStorage.removeItem('transitops-session'); setSession(null); setPage('Dashboard') }
  const mutate = async (work: () => Promise<unknown>, success: string) => {
    try { await work(); setModal(null); setNotice(success); await load() } catch (error) { setNotice(messageFrom(error)) }
  }

  if (!session) return <Login onLogin={login} />

  const choosePage = (target: string) => { setPage(target); setMobileNav(false) }
  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'sidebar-open' : ''}`}>
      <div className="brand"><span className="brand-mark"><ArrowUpRight size={19}/></span><span>Transit<span>Ops</span></span></div>
      <p className="workspace-label">OPERATIONS WORKSPACE</p>
      <nav>{allowedNav.map((item) => <button key={item.key} className={`nav-item ${page === item.key ? 'active' : ''}`} onClick={() => choosePage(item.key)}><item.icon size={18}/><span>{item.key}</span></button>)}</nav>
      <div className="sidebar-bottom"><div className="identity"><div className="avatar">{session.user.name.split(' ').map((name) => name[0]).join('')}</div><div><b>{session.user.name}</b><small>{session.user.role}</small></div></div><button className="logout" onClick={logout}><LogOut size={17}/> Sign out</button></div>
    </aside>
    {mobileNav && <button className="scrim" aria-label="Close navigation" onClick={() => setMobileNav(false)} />}
    <main className="main-content">
      <header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu /></button><div className="search"><Search size={17}/><input placeholder="Search fleet, drivers, trips…" /></div><div className="top-user"><span className="live-dot"/> Live demo</div></header>
      <section className="content">
        {notice && <div className="notice"><span>{notice}</span><button onClick={() => setNotice('')}><X size={16}/></button></div>}
        {loading ? <Loading /> : <Page page={page} dashboard={dashboard} vehicles={vehicles} drivers={drivers} trips={trips} maintenance={maintenance} finance={finance} analytics={analytics} preferences={preferences} user={session.user} onAdd={setModal} onAction={(path: string, label: string) => mutate(() => api.post(path), label)} onSaveSettings={(values: RecordValue) => mutate(() => api.put('/settings', values), 'Workspace preferences saved.')} />}
      </section>
    </main>
    {modal && <Modal title={{ vehicle: 'Add vehicle', driver: 'Add driver', trip: 'Create draft trip', maintenance: 'Log maintenance', fuel: 'Log fuel', expense: 'Add expense' }[modal]} onClose={() => setModal(null)}>
      <EntryForm kind={modal} vehicles={vehicles} drivers={drivers} onSave={(payload) => {
        const route = { vehicle: '/vehicles', driver: '/drivers', trip: '/trips', maintenance: '/maintenance', fuel: '/finance/fuel', expense: '/finance/expenses' }[modal]
        return mutate(() => api.post(route, payload), `${modal === 'trip' ? 'Draft trip' : modal[0].toUpperCase() + modal.slice(1)} saved successfully.`)
      }}/>
    </Modal>}
  </div>
}

function Login({ onLogin }: { onLogin: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState('dispatcher@transitops.demo'); const [password, setPassword] = useState('demo'); const [error, setError] = useState(''); const [busy, setBusy] = useState(false)
  const submit = async (event: FormEvent) => { event.preventDefault(); setBusy(true); setError(''); try { await onLogin(email, password) } catch (reason) { setError(reason instanceof Error ? reason.message : 'Unable to sign in.') } finally { setBusy(false) } }
  return <div className="login-page"><div className="login-intro"><div className="brand"><span className="brand-mark"><ArrowUpRight size={21}/></span><span>Transit<span>Ops</span></span></div><div><p className="eyebrow">SMART TRANSPORT OPERATIONS</p><h1>Run every trip<br/>with confidence.</h1><p>One calm command centre for fleet availability, driver compliance, dispatch decisions and operating costs.</p></div><div className="login-note"><ShieldCheck size={21}/><span>Server-enforced dispatch rules prevent invalid assignments before they happen.</span></div></div><div className="login-panel"><form onSubmit={submit}><p className="eyebrow">WELCOME BACK</p><h2>Sign in to TransitOps</h2><p className="muted">Use a seeded demo account to explore the operational workflow.</p>{error && <div className="form-error">{error}</div>}<label>Work email<input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required /></label><label>Password<input value={password} onChange={(e) => setPassword(e.target.value)} type="password" required /></label><button className="primary full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'} <ChevronRight size={18}/></button><div className="demo-users"><p>QUICK DEMO ROLES</p>{[['dispatcher@transitops.demo', 'Dispatcher'], ['fleet@transitops.demo', 'Fleet Manager'], ['finance@transitops.demo', 'Financial Analyst']].map(([value, label]) => <button type="button" key={value} onClick={() => setEmail(value)}>{label}<span>{value}</span></button>)}</div></form></div></div>
}

function Page(props: RecordValue) {
  const { page } = props
  if (page === 'Dashboard') return <Dashboard {...props}/>
  if (page === 'Fleet') return <Fleet {...props}/>
  if (page === 'Drivers') return <Drivers {...props}/>
  if (page === 'Trips') return <Trips {...props}/>
  if (page === 'Maintenance') return <Maintenance {...props}/>
  if (page === 'Fuel & Expenses') return <Finance {...props}/>
  if (page === 'Analytics') return <><Analytics {...props}/><AnalyticsExport/></>
  return <SettingsPage {...props}/>
}

function AnalyticsExport() {
  const download = async () => {
    const response = await api.get('/analytics/export', { responseType: 'blob' })
    const link = document.createElement('a'); link.href = URL.createObjectURL(response.data); link.download = 'transitops-analytics.csv'; link.click(); URL.revokeObjectURL(link.href)
  }
  return <div className="export-row"><button className="secondary" onClick={download}><Download size={17}/> Export cost ranking CSV</button></div>
}

function Dashboard({ dashboard, onAdd }: RecordValue) {
  const kpis = dashboard?.kpis || {}; const palette = ['#22c55e', '#3b82f6', '#f59e0b', '#ef4444']
  const cards = [['Active vehicles', kpis.activeVehicles, 'Across active fleet'], ['Available now', kpis.availableVehicles, 'Ready to dispatch'], ['In maintenance', kpis.inMaintenance, 'Dispatch blocked'], ['Active trips', kpis.activeTrips, 'Resources reserved'], ['Pending trips', kpis.pendingTrips, 'Awaiting dispatch'], ['Fleet utilization', `${kpis.utilization || 0}%`, 'Vehicles on trip']]
  const icons = [CarFront, CheckCircle2, Wrench, ClipboardList, AlertTriangle, BarChart3]
  return <><section className="page-header"><div><p className="eyebrow">OPERATIONS OVERVIEW</p><h1>Good morning, {dashboard?.viewer?.name?.split(' ')[0] || 'team'}.</h1><p className="muted">Here is the live state of your fleet and delivery operations.</p></div><button className="primary" onClick={() => onAdd('trip')}><Plus size={18}/> New trip</button></section><section className="kpi-grid">{cards.map(([label, value, note], index) => { const Icon = icons[index]; return <article className="kpi-card" key={label}><span className={`kpi-icon tone-${index % 4}`}><Icon size={19}/></span><div><p>{label}</p><h2>{value ?? 0}</h2><small>{note}</small></div></article> })}</section><section className="dashboard-grid"><article className="panel"><div className="panel-heading"><div><h3>Fleet status</h3><p>Availability across the fleet</p></div></div><div className="chart-wrap"><ResponsiveContainer width="100%" height={230}><PieChart><Pie data={dashboard?.vehicleStatus} dataKey="value" nameKey="name" innerRadius={58} outerRadius={86} paddingAngle={4}>{(dashboard?.vehicleStatus || []).map((_: RecordValue, index: number) => <Cell key={index} fill={palette[index]}/>)}</Pie><Tooltip/><text x="50%" y="47%" textAnchor="middle" className="chart-center">{kpis.activeVehicles || 0}</text><text x="50%" y="57%" textAnchor="middle" className="chart-sub">ACTIVE</text></PieChart></ResponsiveContainer></div><div className="legend">{(dashboard?.vehicleStatus || []).map((item: RecordValue, index: number) => <span key={item.name}><i style={{ background: palette[index] }}/>{item.name} <b>{item.value}</b></span>)}</div></article><article className="panel"><div className="panel-heading"><div><h3>Recent trips</h3><p>Latest plans and deliveries</p></div></div><div className="compact-list">{(dashboard?.recentTrips || []).map((trip: RecordValue) => <div className="trip-row" key={trip.id}><div className="trip-icon"><ClipboardList size={17}/></div><div className="trip-main"><b>{trip.id}</b><span>{trip.source} <ChevronRight size={13}/> {trip.destination}</span></div><div><span className={statusClass(trip.status)}>{trip.status}</span><small>{trip.vehicle} · {trip.driver}</small></div></div>)}</div></article></section></>
}

function Fleet({ vehicles, onAdd, onAction }: RecordValue) {
  const [query, setQuery] = useState(''); const [status, setStatus] = useState('All'); const [type, setType] = useState('All')
  const rows = vehicles.filter((v: RecordValue) => (status === 'All' || v.status === status) && (type === 'All' || v.vehicle_type === type) && `${v.name} ${v.registration}`.toLowerCase().includes(query.toLowerCase()))
  return <><Header eyebrow="FLEET REGISTRY" title="Fleet and vehicle health" description="Manage capacity, lifecycle state, and dispatch readiness." action="Add vehicle" onAction={() => onAdd('vehicle')}/><FilterBar query={query} onQuery={setQuery} queryLabel="Search registration or vehicle" filters={[{ value: status, onChange: setStatus, options: ['All','Available','On Trip','In Shop','Retired'] }, { value: type, onChange: setType, options: ['All', ...Array.from(new Set<string>(vehicles.map((v: RecordValue) => String(v.vehicle_type))))] } ]}/><Table empty="No vehicles match these filters." columns={['Vehicle', 'Registration', 'Type', 'Capacity', 'Odometer', 'Status', 'Action']} rows={rows.map((v: RecordValue) => [<b>{v.name}</b>, v.registration, v.vehicle_type, `${v.capacity_kg.toLocaleString()} kg`, `${v.odometer_km.toLocaleString()} km`, <span className={statusClass(v.status)}>{v.status}</span>, v.status === 'Available' || v.status === 'In Shop' ? <button className="small-secondary" onClick={() => { if (window.confirm(`Retire ${v.name}? This cannot be undone in the demo.`)) onAction(`/vehicles/${v.id}/retire`, `${v.name} retired.`) }}>Retire</button> : '—'])}/></>
}
function Drivers({ drivers, onAdd }: RecordValue) {
  const [query, setQuery] = useState(''); const [status, setStatus] = useState('All')
  const rows = drivers.filter((d: RecordValue) => (status === 'All' || d.status === status) && `${d.name} ${d.license_number}`.toLowerCase().includes(query.toLowerCase()))
  return <><Header eyebrow="DRIVER DIRECTORY" title="Compliance and availability" description="Keep verified driver records ready for safe dispatch." action="Add driver" onAction={() => onAdd('driver')}/><FilterBar query={query} onQuery={setQuery} queryLabel="Search name or licence" filters={[{ value: status, onChange: setStatus, options: ['All','Available','On Trip','Off Duty','Suspended'] }]}/><Table empty="No drivers match these filters." columns={['Driver', 'Licence', 'Category', 'Expires', 'Safety', 'Status']} rows={rows.map((d: RecordValue) => [<b>{d.name}</b>, d.license_number, d.license_category, <span className={new Date(d.license_expiry) < new Date() ? 'expired' : ''}>{d.license_expiry}</span>, `${d.safety_score}%`, <span className={statusClass(d.status)}>{d.status}</span>])}/></>
}
function Trips({ trips, onAdd, onAction }: RecordValue) { const states = ['Draft', 'Dispatched', 'Completed', 'Cancelled']; return <><Header eyebrow="TRIP DISPATCHER" title="Plan, dispatch, and complete" description="Availability and cargo capacity are checked again by the server at dispatch." action="New trip" onAction={() => onAdd('trip')}/><div className="workflow-note"><ShieldCheck size={18}/><span>Protected workflow: only Available vehicles and valid, Available drivers can dispatch. Cargo must stay within vehicle capacity.</span></div><div className="trip-board">{states.map((state) => <section className="board-column" key={state}><div className="board-title"><span>{state}</span><b>{trips.filter((t: RecordValue) => t.status === state).length}</b></div>{trips.filter((t: RecordValue) => t.status === state).map((trip: RecordValue) => <article className="trip-card" key={trip.id}><div><b>{trip.id}</b><span className={statusClass(trip.status)}>{trip.status}</span></div><h4>{trip.source} <ChevronRight size={15}/> {trip.destination}</h4><p>{trip.vehicle} · {trip.driver}</p><small>{trip.cargo_kg.toLocaleString()} kg · {trip.planned_distance_km} km</small>{state === 'Draft' && <button className="small-primary" onClick={() => onAction(`/trips/${trip.id}/dispatch`, `${trip.id} dispatched. Vehicle and driver are now On Trip.`)}>Dispatch</button>}{state === 'Dispatched' && <div className="card-actions"><button className="small-primary" onClick={() => onAction(`/trips/${trip.id}/complete`, `${trip.id} completed and resources released.`)}>Complete</button><button className="small-secondary" onClick={() => onAction(`/trips/${trip.id}/cancel`, `${trip.id} cancelled and resources released.`)}>Cancel</button></div>}</article>)}</section>)}</div></> }
function Maintenance({ maintenance, onAdd, onAction }: RecordValue) { return <><Header eyebrow="MAINTENANCE" title="Protect fleet availability" description="Active maintenance immediately moves a vehicle into In Shop." action="Log maintenance" onAction={() => onAdd('maintenance')}/><Table columns={['Vehicle', 'Service', 'Opened', 'Cost', 'Status', 'Action']} rows={maintenance.map((m: RecordValue) => [<b>{m.vehicle}</b>, m.service_type, m.opened_at, currency(m.cost), <span className={statusClass(m.status === 'Active' ? 'In Shop' : 'Completed')}>{m.status}</span>, m.status === 'Active' ? <button className="small-primary" onClick={() => onAction(`/maintenance/${m.id}/close`, `${m.vehicle} is available again.`)}>Close work order</button> : <span className="muted">Closed {m.closed_at}</span>])}/></> }
function Finance({ finance, onAdd }: RecordValue) { return <><Header eyebrow="FUEL & EXPENSES" title="Operating cost, without guesswork" description="Operational cost is Fuel plus Maintenance. Other expenses stay separately visible." action="Log fuel" onAction={() => onAdd('fuel')} secondary="Add expense" onSecondary={() => onAdd('expense')}/><section className="cost-strip"><div><span>Operational cost</span><b>{currency(finance?.operationalCost || 0)}</b><small>Fuel + maintenance</small></div><div><span>Expanded cost</span><b>{currency(finance?.expandedCost || 0)}</b><small>Includes tolls & misc.</small></div></section><div className="two-tables"><Table title="Fuel logs" columns={['Vehicle', 'Date', 'Litres', 'Rate', 'Cost', 'Vendor', 'Receipt']} rows={(finance?.fuelLogs || []).map((f: RecordValue) => [f.vehicle, f.date, String(f.liters) + ' L', f.price_per_liter ? currency(f.price_per_liter) : '-', currency(f.cost), f.vendor || '-', f.receipt_image ? <a href={String(api.defaults.baseURL).replace(/\/api$/, '') + f.receipt_image} target="_blank" rel="noreferrer">View</a> : '-'])}/><Table title="Other expenses" columns={['Category', 'Vehicle', 'Date', 'Amount', 'Notes']} rows={(finance?.expenses || []).map((e: RecordValue) => [e.category, e.vehicle, e.date, currency(e.amount), e.notes || '-'])}/></div></> }
function Analytics({ analytics }: RecordValue) { const metrics = analytics?.metrics || {}; return <><Header eyebrow="REPORTS & ANALYTICS" title="Fleet performance, explained" description="Metrics use the same committed operational records as the dashboard."/><section className="kpi-grid analytics-cards">{[['Fuel efficiency', metrics.fuelEfficiency ? `${metrics.fuelEfficiency} km/L` : 'N/A'], ['Fleet utilization', `${metrics.utilization || 0}%`], ['Operational cost', currency(metrics.operationalCost || 0)], ['Vehicle ROI', metrics.roi === null ? 'N/A' : `${metrics.roi}%`]].map(([label, value], index) => <article className="metric-card" key={label}><span>{label}</span><b className={`metric-${index}`}>{value}</b></article>)}</section><section className="dashboard-grid"><article className="panel"><div className="panel-heading"><div><h3>Monthly revenue</h3><p>Completed and active trip revenue</p></div></div><div className="bar-chart"><ResponsiveContainer width="100%" height={260}><BarChart data={analytics?.revenue || []}><CartesianGrid vertical={false} stroke="#e8edf4"/><XAxis dataKey="month" axisLine={false} tickLine={false}/><YAxis hide/><Tooltip formatter={(value) => currency(Number(value))}/><Bar dataKey="amount" fill="#2f7aef" radius={[6,6,0,0]}/></BarChart></ResponsiveContainer></div></article><article className="panel"><div className="panel-heading"><div><h3>Costliest vehicles</h3><p>Fuel plus maintenance</p></div></div><div className="cost-ranking">{(analytics?.costliestVehicles || []).map((item: RecordValue, index: number) => <div key={item.vehicle}><div><span>{index + 1}</span><b>{item.vehicle}</b><strong>{currency(item.cost)}</strong></div><i><em style={{ width: `${Math.max(8, item.cost / Math.max(...analytics.costliestVehicles.map((x: RecordValue) => x.cost)) * 100)}%` }}/></i></div>)}</div></article></section></> }
function SettingsPage({ user, preferences, onSaveSettings }: RecordValue) {
  const [values, setValues] = useState<RecordValue>(preferences || { depot_name: '', currency: 'INR', distance_unit: 'Kilometres' })
  useEffect(() => setValues(preferences || { depot_name: '', currency: 'INR', distance_unit: 'Kilometres' }), [preferences])
  return <><Header eyebrow="SETTINGS & RBAC" title="Workspace preferences" description="Role permissions are visible here; authorization is enforced by the API."/><section className="settings-grid"><form className="panel preference-card" onSubmit={(event) => { event.preventDefault(); onSaveSettings(values) }}><h3>General</h3><label>Depot name<input value={values.depot_name || ''} onChange={(event) => setValues({ ...values, depot_name: event.target.value })} required/></label><label>Currency<select value={values.currency || 'INR'} onChange={(event) => setValues({ ...values, currency: event.target.value })}><option value="INR">INR</option><option value="USD">USD</option></select></label><label>Distance unit<select value={values.distance_unit || 'Kilometres'} onChange={(event) => setValues({ ...values, distance_unit: event.target.value })}><option>Kilometres</option><option>Miles</option></select></label><button className="primary">Save changes</button></form><article className="panel"><h3>Role-based access</h3><p className="muted">Signed in as <b>{user.role}</b></p><div className="rbac"><div className="rbac-head"><span>Role</span><span>Fleet</span><span>Drivers</span><span>Trips</span><span>Finance</span><span>Analytics</span></div>{[['Fleet Manager','Full','Full','Read','Read','Read'],['Dispatcher','Read','-','Full','-','-'],['Safety Officer','-','Full','Read','-','-'],['Financial Analyst','Read','-','-','Full','Full']].map((row) => <div key={row[0]}>{row.map((cell) => <span key={cell}>{cell === 'Full' ? <CheckCircle2 size={16}/> : cell}</span>)}</div>)}</div></article></section></> }

function Header({ eyebrow, title, description, action, onAction, secondary, onSecondary, actionIcon }: RecordValue) { return <section className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action && <div className="header-actions">{secondary && <button className="secondary" onClick={onSecondary}><Plus size={17}/>{secondary}</button>}<button className="primary" onClick={onAction}>{actionIcon || <Plus size={18}/>}{action}</button></div>}</section> }
function FilterBar({ query, onQuery, queryLabel, filters }: { query: string; onQuery: (value: string) => void; queryLabel: string; filters: { value: string; onChange: (value: string) => void; options: string[] }[] }) { return <div className="filter-bar"><label><Search size={16}/><input value={query} onChange={(event) => onQuery(event.target.value)} placeholder={queryLabel}/></label>{filters.map((filter, index) => <select key={index} value={filter.value} onChange={(event) => filter.onChange(event.target.value)}>{filter.options.map((option) => <option key={option}>{option}</option>)}</select>)}</div> }
function Table({ title, columns, rows, empty }: { title?: string; columns: string[]; rows: React.ReactNode[][]; empty?: string }) { return <article className="panel table-panel">{title && <div className="panel-heading"><div><h3>{title}</h3></div></div>}<div className="table-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={index}>{row.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>) : <tr><td colSpan={columns.length} className="empty-cell">{empty || 'No records yet.'}</td></tr>}</tbody></table></div></article> }
function Modal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) { return <div className="modal-backdrop"><div className="modal"><div className="modal-heading"><div><p className="eyebrow">NEW RECORD</p><h2>{title}</h2></div><button onClick={onClose} aria-label="Close"><X/></button></div>{children}</div></div> }
function EntryForm({ kind, vehicles, drivers, onSave }: { kind: string; vehicles: RecordValue[]; drivers: RecordValue[]; onSave: (payload: RecordValue) => void }) {
  if (kind === 'fuel') return <FuelEntryForm api={api} vehicles={vehicles} onSave={onSave}/>
  const [payload, setPayload] = useState<RecordValue>(() => ({ status: 'Available', region: 'Ahmedabad', license_expiry: '2027-12-31', safety_score: 90, vehicle_id: vehicles.find((v) => v.status === 'Available')?.id || '', driver_id: drivers.find((d) => d.status === 'Available')?.id || '', category: 'Toll' }))
  const set = (key: string, value: string) => setPayload((current) => ({ ...current, [key]: value }))
  const fields: Record<string, [string, string, string?][]> = { vehicle: [['registration','Registration','text'],['name','Vehicle name','text'],['vehicle_type','Type','text'],['capacity_kg','Capacity (kg)','number'],['odometer_km','Odometer (km)','number'],['acquisition_cost','Acquisition cost','number'],['region','Region','text']], driver: [['name','Full name','text'],['license_number','Licence number','text'],['license_category','Licence category','text'],['license_expiry','Licence expiry','date'],['contact','Contact','tel'],['safety_score','Safety score','number'],['region','Region','text']], trip: [['source','Source','text'],['destination','Destination','text'],['cargo_kg','Cargo weight (kg)','number'],['planned_distance_km','Planned distance (km)','number'],['revenue','Expected revenue','number'],['notes','Notes','text']], maintenance: [['service_type','Service type','text'],['cost','Estimated cost','number'],['notes','Notes','text']], fuel: [['liters','Litres','number'],['cost','Total cost','number'],['odometer_km','Odometer (km)','number'],['vendor','Vendor','text']], expense: [['amount','Amount','number'],['notes','Notes','text']] }
  const save = (event: FormEvent) => { event.preventDefault(); const numeric = ['capacity_kg','odometer_km','acquisition_cost','safety_score','cargo_kg','planned_distance_km','revenue','cost','liters','amount']; const parsed = Object.fromEntries(Object.entries(payload).map(([key,value]) => [key, numeric.includes(key) && value !== '' ? Number(value) : value])); onSave(parsed) }
  return <form className="entry-form" onSubmit={save}>{(kind === 'trip' || kind === 'maintenance' || kind === 'fuel') && <label>Vehicle<select value={payload.vehicle_id} onChange={(event) => set('vehicle_id', event.target.value)} required><option value="">Select vehicle</option>{vehicles.map((vehicle) => <option value={vehicle.id} key={vehicle.id}>{vehicle.name} · {vehicle.status}</option>)}</select></label>}{kind === 'trip' && <label>Driver<select value={payload.driver_id} onChange={(event) => set('driver_id', event.target.value)} required><option value="">Select driver</option>{drivers.map((driver) => <option value={driver.id} key={driver.id}>{driver.name} · {driver.status}</option>)}</select></label>}{kind === 'expense' && <label>Category<select value={payload.category} onChange={(event) => set('category', event.target.value)}><option>Toll</option><option>Miscellaneous</option></select></label>}{fields[kind].map(([key, label, type]) => <label key={key}>{label}<input value={payload[key] ?? ''} onChange={(event) => set(key, event.target.value)} type={type || 'text'} required={['registration','name','vehicle_type','capacity_kg','license_number','source','destination','service_type','liters','cost','amount'].includes(key)}/></label>)}<button className="primary full" type="submit">Save record <ChevronRight size={18}/></button></form>
}
function Loading() { return <div className="loading"><div/><p>Loading operational data…</p></div> }

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
