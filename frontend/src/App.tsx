import { useRef, useState } from 'react'
import type { ChangeEvent, DragEvent, ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { NavLink, Route, Routes } from 'react-router-dom'
import {
  Activity, AlertTriangle, ArrowDownUp, BarChart3, Camera, Car, CheckCircle2,
  ChevronRight, CircleGauge, Database, Download, FileSearch, Film, Gauge,
  HardDrive, HeartPulse, LayoutDashboard, Menu, OctagonAlert, Pause, Play,
  Radio, RefreshCw, Search, Settings, ShieldCheck, SlidersHorizontal, Square,
  UploadCloud, Video, X, Zap,
} from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, formatBytes, pct } from './lib/api'
import { useAppStore } from './lib/store'
import type { Analytics, Health, Incident, Job, Video as VideoType } from './types'

const nav = [
  ['Overview', '/', LayoutDashboard], ['Video analysis', '/analysis', Film],
  ['Live monitoring', '/live', Radio], ['Camera studio', '/studio', SlidersHorizontal],
  ['Incident review', '/incidents', AlertTriangle], ['Traffic analytics', '/analytics', BarChart3],
  ['Plate search', '/plates', FileSearch], ['System health', '/health', HeartPulse],
  ['Settings', '/settings', Settings],
] as const

const modules = [
  ['collision', 'Possible collisions'], ['congestion', 'Congestion & queues'],
  ['vehicle_counting', 'Vehicle counting'], ['speed', 'Speed & abnormal speed'],
  ['parking', 'Illegal parking'], ['wrong_way', 'Wrong-way & U-turns'],
  ['red_light', 'Red light & stop line'], ['lane', 'Lane violations'],
  ['intrusion', 'Vulnerable road users'], ['hazard', 'Road hazards'],
] as const

function cx(...values: Array<string | false | undefined>) { return values.filter(Boolean).join(' ') }

function Shell({ children }: { children: ReactNode }) {
  const { sidebarOpen, toggleSidebar, demoMode, setDemoMode } = useAppStore()
  const health = useQuery({ queryKey: ['health'], queryFn: () => api<Health>('/health'), refetchInterval: 15_000 })
  return <div className="app-shell">
    <aside className={cx('sidebar', !sidebarOpen && 'sidebar--closed')}>
      <div className="brand"><div className="brand-mark"><ArrowDownUp size={19}/></div><div><strong>TRAFFICVISION</strong><span>LOCAL OPERATIONS</span></div></div>
      <nav>{nav.map(([label, to, Icon]) => <NavLink key={to} to={to} end={to === '/'} className={({isActive}) => cx('nav-item', isActive && 'active')}><Icon size={18}/><span>{label}</span></NavLink>)}</nav>
      <div className="sidebar-foot"><span className={cx('status-dot', health.data?.status === 'healthy' && 'online')}/><div><strong>{health.data?.status === 'healthy' ? 'Systems operational' : 'Backend unavailable'}</strong><span>{health.data?.local_only === false ? 'Network exposure warning' : 'Local processing only'}</span></div></div>
    </aside>
    <section className="workspace">
      <header className="topbar"><button className="icon-button" onClick={toggleSidebar} aria-label="Toggle navigation"><Menu size={19}/></button><div className="topbar-spacer"/><label className={cx('mode-toggle', demoMode && 'demo')}><input type="checkbox" checked={demoMode} onChange={e => setDemoMode(e.target.checked)}/><span>{demoMode ? 'SIMULATION / DEMO' : 'REAL ANALYSIS'}</span></label><div className="operator"><div className="operator-avatar">OP</div><div><strong>Local operator</strong><span>Human review required</span></div></div></header>
      <main>{children}</main>
    </section>
  </div>
}

function Header({ eyebrow, title, description, actions }: { eyebrow: string; title: string; description: string; actions?: ReactNode }) {
  return <div className="page-header"><div><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p>{description}</p></div>{actions && <div className="header-actions">{actions}</div>}</div>
}

function Card({ children, className, title, action }: { children: ReactNode; className?: string; title?: string; action?: ReactNode }) {
  return <section className={cx('card', className)}>{title && <div className="card-head"><h2>{title}</h2>{action}</div>}{children}</section>
}

function Metric({ label, value, meta, icon: Icon, tone = 'cyan' }: { label: string; value: ReactNode; meta: string; icon: typeof Activity; tone?: string }) {
  return <Card className="metric"><div className={`metric-icon ${tone}`}><Icon size={18}/></div><span>{label}</span><strong>{value}</strong><small>{meta}</small></Card>
}

function Empty({ icon: Icon, title, text, action }: { icon: typeof Activity; title: string; text: string; action?: ReactNode }) {
  return <div className="empty"><div className="empty-icon"><Icon size={23}/></div><strong>{title}</strong><p>{text}</p>{action}</div>
}

function Overview() {
  const analytics = useQuery({ queryKey: ['analytics'], queryFn: () => api<Analytics>('/analytics') })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/jobs'), refetchInterval: 2500 })
  const incidents = useQuery({ queryKey: ['incidents'], queryFn: () => api<Incident[]>('/incidents') })
  const data = analytics.data
  const active = jobs.data?.filter(job => ['queued', 'processing'].includes(job.status)) ?? []
  return <>
    <Header eyebrow="COMMAND OVERVIEW" title="Traffic operations" description="Local computer vision, evidence review, and calibrated road analytics." actions={<span className="pill good"><ShieldCheck size={14}/> Local & private</span>}/>
    <div className="notice amber"><AlertTriangle size={18}/><div><strong>Human review is mandatory</strong><span>All incidents are possible detections. Nothing is automatically confirmed, fined, or sent.</span></div></div>
    <div className="metric-grid">
      <Metric label="Vehicles tracked" value={data?.total_tracks ?? 0} meta="Unique persistent tracks" icon={Car}/>
      <Metric label="Active jobs" value={active.length} meta={`${data?.completed_jobs ?? 0} completed`} icon={Activity} tone="green"/>
      <Metric label="New incidents" value={incidents.data?.filter(x => x.review_status === 'New').length ?? 0} meta="Awaiting operator review" icon={OctagonAlert} tone="amber"/>
      <Metric label="Plate read rate" value={pct(data?.plate_success_rate)} meta={data?.plate_reads ? `${data.plate_reads} vehicle attempts` : 'No real OCR attempts yet'} icon={FileSearch} tone="red"/>
    </div>
    <div className="dashboard-grid">
      <Card title="Active processing" action={<NavLink to="/analysis" className="text-link">Open analysis <ChevronRight size={15}/></NavLink>}>
        {!active.length ? <Empty icon={Film} title="No processing jobs" text="Upload your first traffic video to begin local analysis."/> : active.map(job => <div className="job-row" key={job.id}><div className="job-icon"><Film size={18}/></div><div className="job-main"><strong>{job.active_module}</strong><span>{job.processed_frames.toLocaleString()} / {job.total_frames.toLocaleString()} frames</span><div className="progress"><i style={{width: `${job.progress * 100}%`}}/></div></div><b>{pct(job.progress)}</b></div>)}
      </Card>
      <Card title="Recent alerts" action={<NavLink to="/incidents" className="text-link">Review queue <ChevronRight size={15}/></NavLink>}>
        {!incidents.data?.length ? <Empty icon={CheckCircle2} title="Review queue is clear" text="Real incidents will appear only when evidence meets configured rule thresholds."/> : incidents.data.slice(0, 5).map(item => <div className="alert-row" key={item.id}><span className={`severity ${item.severity}`}/><div><strong>{item.category}</strong><span>{item.plate_text} · {pct(item.confidence)}</span></div><span className="pill">{item.review_status}</span></div>)}
      </Card>
    </div>
    <Card title="Readiness by capability"><div className="readiness-grid">
      {[['Object detection', 'Ready', 'green'], ['Persistent tracking', 'ByteTrack', 'green'], ['Plate OCR', 'Operator opt-in', 'amber'], ['Speed enforcement', 'Needs calibration', 'amber'], ['Hazard model', 'Limited support', 'red']].map(([a,b,c]) => <div className="readiness" key={a}><span className={`status-dot ${c}`}/><div><strong>{a}</strong><span>{b}</span></div></div>)}
    </div></Card>
  </>
}

function VideoAnalysis() {
  const client = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const [selected, setSelected] = useState<string[]>(modules.map(([key]) => key))
  const [profile, setProfile] = useState('CPU Light')
  const [configurationId, setConfigurationId] = useState('')
  const [plateOcr, setPlateOcr] = useState(false)
  const [privacy, setPrivacy] = useState(false)
  const [currentJob, setCurrentJob] = useState<string | null>(null)
  const videos = useQuery({ queryKey: ['videos'], queryFn: () => api<VideoType[]>('/videos') })
  const configurations = useQuery({ queryKey: ['camera-configurations'], queryFn: () => api<Array<{id:string;name:string}>>('/camera-configurations') })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => api<Job[]>('/jobs'), refetchInterval: 1500 })
  const upload = useMutation({
    mutationFn: async () => {
      if (!file) throw new Error('Choose a video first')
      const body = new FormData(); body.append('file', file)
      return api<{id: string}>('/videos/upload', { method: 'POST', body })
    },
    onSuccess: async result => {
      const job = await api<Job>(`/videos/${result.id}/analysis`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ modules: selected, configuration_id: configurationId || null, performance_profile: profile, frame_skip: profile === 'GPU Accuracy' ? 1 : profile === 'CPU Light' ? 3 : 2, inference_size: profile === 'GPU Accuracy' ? 960 : 640, detection_confidence: profile === 'GPU Accuracy' ? 0.18 : 0.35, enable_plate_ocr: plateOcr, privacy_acknowledged: privacy }) })
      setCurrentJob(job.id); client.invalidateQueries({queryKey:['videos']}); client.invalidateQueries({queryKey:['jobs']})
    },
  })
  const activeJob = jobs.data?.find(job => job.id === currentJob) ?? jobs.data?.find(job => job.status === 'processing')
  const jobDetail = useQuery({ queryKey: ['job', activeJob?.id], queryFn: () => api<Job>(`/jobs/${activeJob!.id}`), enabled: Boolean(activeJob), refetchInterval: activeJob?.status === 'processing' ? 1500 : false })
  function takeFile(value?: File) {
    if (!value) return
    if (!['.mp4','.mov','.avi','.mkv'].some(ext => value.name.toLowerCase().endsWith(ext))) return alert('Choose MP4, MOV, AVI, or MKV footage.')
    setFile(value)
  }
  return <>
    <Header eyebrow="VIDEO PIPELINE" title="Analyze recorded footage" description="Upload, probe, track, evaluate rules, and preserve reviewable evidence locally."/>
    <div className="analysis-layout">
      <div className="stack">
        <Card title="1 · Source footage">
          <div className="dropzone" onDragOver={e => e.preventDefault()} onDrop={(e: DragEvent) => { e.preventDefault(); takeFile(e.dataTransfer.files[0]) }}>
            <UploadCloud size={30}/><strong>{file ? file.name : 'Drop traffic footage here'}</strong><span>{file ? formatBytes(file.size) : 'MP4, MOV, AVI, or MKV · up to 8 GB'}</span><label className="button secondary">Browse files<input hidden type="file" accept=".mp4,.mov,.avi,.mkv" onChange={(e: ChangeEvent<HTMLInputElement>) => takeFile(e.target.files?.[0])}/></label>
          </div>
          {videos.data?.length ? <div className="recent-files"><span>RECENT SOURCES</span>{videos.data.slice(0,3).map(video => <div key={video.id}><Film size={15}/><strong>{video.display_name}</strong><small>{video.width}×{video.height} · {video.fps?.toFixed(1) ?? '?'} fps</small></div>)}</div> : null}
        </Card>
        <Card title="2 · Analysis modules"><div className="module-grid">{modules.map(([key,label]) => <label className={cx('module-check', selected.includes(key) && 'selected')} key={key}><input type="checkbox" checked={selected.includes(key)} onChange={() => setSelected(x => x.includes(key) ? x.filter(v => v !== key) : [...x,key])}/><span><CheckCircle2 size={16}/></span>{label}</label>)}</div></Card>
        <Card title="3 · Route configuration & processing"><label className="configuration-select"><span><strong>Camera / route geometry</strong><small>Choose saved zones and calibration for scene-specific rules.</small></span><select value={configurationId} onChange={e=>setConfigurationId(e.target.value)}><option value="">None — tracking and OCR only</option>{configurations.data?.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select></label><div className="profile-grid">{['CPU Light','CPU Balanced','GPU Balanced','GPU Accuracy'].map(item => <button key={item} className={cx('profile', profile === item && 'selected')} onClick={() => setProfile(item)}><CircleGauge size={19}/><strong>{item}</strong><span>{item.includes('GPU') ? 'Used only when CUDA is available' : item === 'CPU Light' ? 'Fastest, skips more frames' : 'More frequent inference'}</span></button>)}</div></Card>
        <Card title="4 · License plate recognition">
          <label className="setting-row"><div><strong>Detect and read plates inside vehicle crops</strong><span>Generic letters and digits; not restricted to a country format.</span></div><input className="switch" type="checkbox" checked={plateOcr} onChange={e => setPlateOcr(e.target.checked)}/></label>
          {plateOcr && <label className="privacy-check"><input type="checkbox" checked={privacy} onChange={e => setPrivacy(e.target.checked)}/><span>I understand plates may be identifiable information. Processing and storage remain local.</span></label>}
        </Card>
        {upload.error && <div className="notice red"><X size={18}/><div><strong>Could not start analysis</strong><span>{upload.error.message}</span></div></div>}
        <button className="button primary large" disabled={!file || !selected.length || upload.isPending || (plateOcr && !privacy)} onClick={() => upload.mutate()}><Play size={18}/>{upload.isPending ? 'Uploading and probing…' : 'Start local analysis'}</button>
      </div>
      <div className="stack sticky-col">
        <Card title="Processing monitor">
          {!activeJob ? <Empty icon={Activity} title="Standing by" text="Progress, measured throughput, and processing logs will appear here."/> : <div className="monitor"><div className="monitor-head"><span className={`job-state ${activeJob.status}`}>{activeJob.status}</span><strong>{pct(activeJob.progress)}</strong></div><h3>{activeJob.active_module}</h3><div className="progress big"><i style={{width:`${activeJob.progress*100}%`}}/></div><div className="monitor-stats"><div><span>Frames</span><strong>{activeJob.processed_frames.toLocaleString()} / {activeJob.total_frames.toLocaleString()}</strong></div><div><span>Processing FPS</span><strong>{activeJob.processing_fps.toFixed(1)}</strong></div></div>{activeJob.error_message && <div className="inline-error">{activeJob.error_message}</div>}<div className="monitor-actions">{activeJob.status === 'processing' && <button className="button danger" onClick={() => api(`/jobs/${activeJob.id}/cancel`,{method:'POST'}).then(()=>client.invalidateQueries({queryKey:['jobs']}))}><Square size={14}/> Cancel safely</button>}{activeJob.output_available && <a className="button secondary" href={`/api/jobs/${activeJob.id}/output`}><Download size={14}/> Annotated result</a>}</div></div>}
        </Card>
        {activeJob && <Card title="Processing log"><div className="processing-log">{jobDetail.data?.logs?.length ? jobDetail.data.logs.slice(-8).map((log,index)=><div key={index}><span>{new Date(log.created_at).toLocaleTimeString()}</span><b className={log.level.toLowerCase()}>{log.level}</b><p>{log.message}</p></div>) : <span>Waiting for pipeline messages…</span>}</div></Card>}
        <div className="notice cyan"><ShieldCheck size={18}/><div><strong>No plate, speed, or incident is invented</strong><span>Weak OCR becomes Unreadable or Insufficient confidence. Speed needs route calibration.</span></div></div>
      </div>
    </div>
  </>
}

type Point = {x:number;y:number}
type StudioShape = {type:string;points:Point[]}
function CameraStudio() {
  const [tool,setTool] = useState('Road region')
  const [points,setPoints] = useState<Point[]>([])
  const [shapes,setShapes] = useState<StudioShape[]>([])
  const [name,setName] = useState('Route 01 configuration')
  const [speedLimit,setSpeedLimit] = useState(50)
  const [distance,setDistance] = useState(0)
  const [saved,setSaved] = useState('')
  const [videoId,setVideoId] = useState('')
  const studioVideos = useQuery({queryKey:['videos'],queryFn:()=>api<VideoType[]>('/videos')})
  const selectedVideo = studioVideos.data?.find(video=>video.id===videoId)
  const originalWidth = selectedVideo?.width ?? 1920
  const originalHeight = selectedVideo?.height ?? 1080
  const editor = useRef<HTMLDivElement>(null)
  const allShapes = points.length ? [...shapes,{type:tool,points}] : shapes
  const referencePoints = points.length >= 2 ? points : [...allShapes].reverse().find(shape=>shape.type==='Calibration points')?.points ?? []
  const speedRegion = [...allShapes].reverse().find(shape=>shape.type==='Speed region')?.points ?? []
  const save = useMutation({ mutationFn: () => api<{id:string}>('/camera-configurations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,original_width:originalWidth,original_height:originalHeight,config:{video_id:videoId||null,shapes:allShapes,speed_limit_kph:speedLimit,reference_distance_m:distance || null,calibration_status:distance > 0 && referencePoints.length >= 2 ? 'measured reference' : 'uncalibrated'}})}), onSuccess: async data => { setSaved(data.id); if(distance > 0 && referencePoints.length >= 2) await api('/calibrations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({configuration_id:data.id,method:'measured_reference',reference:{image_points:referencePoints.slice(0,2).map(p=>[p.x,p.y]),distance_m:distance},speed_region:speedRegion.map(p=>[p.x,p.y]),speed_limit_kph:speedLimit,confidence:.6})}) } })
  const click = (event: React.MouseEvent) => { const box=editor.current?.getBoundingClientRect(); if(!box)return; setPoints(p=>[...p,{x:+((event.clientX-box.left)/box.width).toFixed(4),y:+((event.clientY-box.top)/box.height).toFixed(4)}]) }
  return <>
    <Header eyebrow="CAMERA CONFIGURATION" title="Geometry & calibration studio" description="Draw normalized road geometry once; reuse it for every video from the same fixed camera." actions={<button className="button primary" onClick={()=>save.mutate()} disabled={!allShapes.length}><CheckCircle2 size={15}/> Save configuration</button>}/>
    <div className="studio-layout"><div className="tool-rail"><span>DRAW TOOLS</span>{['Road region','Lane','Direction arrow','Stop line','Traffic light','Crosswalk','Parking space','No-parking zone','Emergency lane','Bus-only lane','Hazard region','Pedestrian restriction','Counting line','Speed region','Calibration points'].map(item=><button className={cx(tool===item&&'active')} onClick={()=>{setTool(item);setPoints([])}} key={item}><ChevronRight size={13}/>{item}</button>)}</div>
    <div className="studio-center"><div className="video-canvas" ref={editor} onClick={click} style={videoId?{backgroundImage:`linear-gradient(rgba(5,9,10,.28),rgba(5,9,10,.28)),url(/api/videos/${videoId}/frame)`,backgroundSize:'contain',backgroundPosition:'center',backgroundRepeat:'no-repeat'}:undefined}><div className="camera-grid"/>{!videoId&&<div className="canvas-empty"><Camera size={32}/><strong>Reference frame arrives with your video</strong><span>Upload footage, then select it in the inspector.</span></div>}<svg viewBox="0 0 1000 562" preserveAspectRatio="none">{shapes.map((shape,index)=><polyline key={index} points={shape.points.map(p=>`${p.x*1000},${p.y*562}`).join(' ')} fill="rgba(89,112,121,.08)" stroke="#627981" strokeWidth="2"/>)}<polyline points={points.map(p=>`${p.x*1000},${p.y*562}`).join(' ')} fill={tool.includes('line')||tool.includes('arrow')?'none':'rgba(39,197,169,.12)'} stroke="#27c5a9" strokeWidth="3"/>{points.map((p,i)=><circle key={i} cx={p.x*1000} cy={p.y*562} r="7" fill="#091113" stroke="#55e4c8" strokeWidth="3"/>)}</svg><div className="canvas-label">{tool.toUpperCase()} · {points.length} POINTS · {shapes.length} SAVED SHAPES</div></div><div className="canvas-actions"><button className="button primary" disabled={points.length<2} onClick={()=>{setShapes(s=>[...s,{type:tool,points}]);setPoints([])}}>Add shape</button><button className="button secondary" onClick={()=>setPoints(p=>p.slice(0,-1))}>Undo point</button><button className="button ghost" onClick={()=>setPoints([])}>Clear shape</button><span>Coordinates are stored relative to {originalWidth}×{originalHeight}</span></div></div>
    <div className="inspector"><span>CONFIGURATION</span><label>Reference video<select value={videoId} onChange={e=>setVideoId(e.target.value)}><option value="">No video · 1920×1080 template</option>{studioVideos.data?.map(video=><option key={video.id} value={video.id}>{video.display_name} · {video.width}×{video.height}</option>)}</select></label><label>Name<input value={name} onChange={e=>setName(e.target.value)}/></label><label>Speed limit (km/h)<input type="number" value={speedLimit} onChange={e=>setSpeedLimit(+e.target.value)}/></label><label>Known route distance (m)<input type="number" min="0" step="0.1" value={distance} onChange={e=>setDistance(+e.target.value)}/><small>Leave 0 until you provide the measured distance.</small></label><div className="calibration-state"><Gauge size={18}/><div><strong>{distance > 0 ? 'Reference entered' : 'Uncalibrated'}</strong><span>{distance > 0 ? 'Select matching points/lines before speed is valid.' : 'No enforceable speed result will be created.'}</span></div></div><label>Current shape<textarea readOnly value={JSON.stringify(points,null,2)}/></label>{saved&&<div className="save-success">Saved as {saved.slice(0,8)}</div>}</div></div>
  </>
}

function IncidentReview() {
  const {demoMode} = useAppStore(); const client=useQueryClient(); const [selected,setSelected]=useState<Incident|null>(null)
  const query=useQuery({queryKey:['incidents',demoMode],queryFn:()=>api<Incident[]>(`/incidents?include_simulation=${demoMode}`)})
  const seed=useMutation({mutationFn:()=>api('/simulation/reset',{method:'POST'}),onSuccess:()=>client.invalidateQueries({queryKey:['incidents']})})
  const update=(item:Incident,status:string)=>api<Incident>(`/incidents/${item.id}`,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({review_status:status,operator_notes:item.operator_notes})}).then(()=>client.invalidateQueries({queryKey:['incidents']}))
  return <><Header eyebrow="EVIDENCE DESK" title="Incident review" description="Confirm, reject, or request evidence. AI findings remain provisional until you decide." actions={demoMode?<button className="button secondary" onClick={()=>seed.mutate()}><RefreshCw size={15}/> Generate synthetic examples</button>:undefined}/>{demoMode&&<div className="notice purple"><Zap size={18}/><div><strong>Simulation / Demo Mode</strong><span>Synthetic incidents are visibly separated and never represented as real analysis.</span></div></div>}
  <div className="review-layout"><Card className="incident-table"><div className="table-toolbar"><div className="searchbox"><Search size={16}/><input placeholder="Search category or plate"/></div><button className="button ghost"><SlidersHorizontal size={15}/> Filters</button></div>{!query.data?.length?<Empty icon={AlertTriangle} title={demoMode?'No simulation examples yet':'No real incidents'} text={demoMode?'Generate explicitly labeled synthetic records for the portfolio demo.':'Incidents appear only after configured rule evaluation on real footage.'}/>:<div className="table"><div className="table-header"><span>Incident</span><span>Type</span><span>Plate</span><span>Confidence</span><span>Status</span></div>{query.data.map(item=><button key={item.id} className={cx('table-row',selected?.id===item.id&&'selected')} onClick={()=>setSelected(item)}><span><strong>{item.incident_number}</strong><small>{new Date(item.created_at).toLocaleString()}</small></span><span>{item.category}</span><span className="plate-text">{item.plate_text}</span><span>{pct(item.confidence)}</span><span><i className="pill">{item.review_status}</i></span></button>)}</div>}</Card>
  <Card className="review-panel" title="Evidence inspector">{!selected?<Empty icon={FileSearch} title="Select an incident" text="Evidence, measurements, OCR alternatives, and review controls appear here."/>:<><div className="evidence-placeholder"><Video size={28}/><strong>{selected.is_simulation?'Synthetic evidence placeholder':'Evidence clip unavailable'}</strong><span>Frame-by-frame controls activate when a real evidence clip exists.</span><div className="player-controls"><button><Play size={15}/></button><div/><span>00:00.000</span></div></div><div className="evidence-facts"><div><span>PLATE RESULT</span><strong>{selected.plate_text}</strong><small>{selected.plate_confidence?`${pct(selected.plate_confidence)} OCR confidence`:'No reliable OCR read'}</small></div><div><span>INCIDENT CONFIDENCE</span><strong>{pct(selected.confidence)}</strong><small>Requires human judgment</small></div></div><div className="measurement-list">{Object.entries(selected.measurements).map(([key,value])=><div key={key}><span>{key.replaceAll('_',' ')}</span><strong>{String(value)}</strong></div>)}</div><label className="notes">Operator notes<textarea value={selected.operator_notes} onChange={e=>setSelected({...selected,operator_notes:e.target.value})} placeholder="Record your evidence-based decision…"/></label><div className="review-actions"><button className="button success" onClick={()=>update(selected,'Confirmed')}><CheckCircle2 size={15}/> Confirm</button><button className="button danger" onClick={()=>update(selected,'Rejected')}><X size={15}/> Reject</button><button className="button secondary" onClick={()=>update(selected,'Needs more evidence')}>Need evidence</button></div><a className="button ghost full" href={`/api/incidents/${selected.id}/report`}><Download size={15}/> Generate draft PDF</a></>}</Card></div></>
}

function AnalyticsPage(){ const q=useQuery({queryKey:['analytics'],queryFn:()=>api<Analytics>('/analytics')}); const data=q.data?.class_distribution??[]; return <><Header eyebrow="TRAFFIC INTELLIGENCE" title="Traffic analytics" description="Measured summaries from persistent real-video tracks; simulation records are excluded." actions={<a className="button secondary" href="/api/analytics/vehicle-counts.csv"><Download size={15}/> Export CSV</a>}/><div className="metric-grid"><Metric label="Completed videos" value={q.data?.completed_jobs??0} meta={`${q.data?.jobs??0} total jobs`} icon={Film}/><Metric label="Unique tracks" value={q.data?.total_tracks??0} meta="Across analyzed footage" icon={Car} tone="green"/><Metric label="Real incidents" value={q.data?.real_incidents??0} meta="Provisional findings" icon={AlertTriangle} tone="amber"/><Metric label="OCR success" value={pct(q.data?.plate_success_rate)} meta="Confidence-qualified reads" icon={FileSearch} tone="red"/></div><div className="dashboard-grid"><Card title="Vehicle class distribution"><div className="chart">{data.length?<ResponsiveContainer><BarChart data={data}><CartesianGrid stroke="#253036" vertical={false}/><XAxis dataKey="name" stroke="#718087"/><YAxis stroke="#718087"/><Tooltip contentStyle={{background:'#11191d',border:'1px solid #26343a'}}/><Bar dataKey="value" fill="#31c7ad" radius={[4,4,0,0]}/></BarChart></ResponsiveContainer>:<Empty icon={BarChart3} title="No track data yet" text="Class distribution populates after real analysis."/>}</div></Card><Card title="Measurement readiness"><div className="analytics-list">{[['Vehicle volume','Ready after tracking'],['Congestion history','Requires road region'],['Speed distribution','Requires calibration'],['Directional flow','Requires counting lines'],['Parking duration','Requires parking zones'],['Camera comparison','Requires multiple camera profiles']].map(([a,b])=><div key={a}><span>{a}</span><strong>{b}</strong></div>)}</div></Card></div></> }

function PlateSearch(){const [term,setTerm]=useState('');const q=useQuery({queryKey:['plates',term],queryFn:()=>api<Array<{id:string;text:string;confidence:number;status:string;alternatives:Array<{text:string;confidence:number}>;created_at:string;crop_available:boolean}>>(`/plates?q=${encodeURIComponent(term)}`)});return <><Header eyebrow="LOCAL OCR INDEX" title="Plate search" description="Search confidence-qualified OCR candidates and trace them back to local tracks and incidents."/><div className="notice amber"><AlertTriangle size={18}/><div><strong>OCR matches may be inaccurate</strong><span>Use the saved crop and alternate readings; never rely on plate text alone.</span></div></div><Card><div className="plate-search"><Search size={20}/><input value={term} onChange={e=>setTerm(e.target.value)} placeholder="Enter all or part of a plate candidate"/></div>{!q.data?.length?<Empty icon={FileSearch} title="No matching plate reads" text="Plate OCR is opt-in and runs only on useful vehicle crops from supplied videos."/>:<div className="plate-results">{q.data.map(row=><div key={row.id}>{row.crop_available?<img src={`/api/plates/${row.id}/crop`} alt="Best plate crop"/>:<div className="crop-empty">NO CROP</div>}<div><strong>{row.text}</strong><span>{row.status} · {pct(row.confidence)}</span><small>{new Date(row.created_at).toLocaleString()}</small></div><div className="alternates">{row.alternatives.map(x=><span key={x.text}>{x.text} {pct(x.confidence)}</span>)}</div></div>)}</div>}</Card></>}

function SystemHealth(){const health=useQuery({queryKey:['health'],queryFn:()=>api<Health>('/health'),refetchInterval:5000});const models=useQuery({queryKey:['models'],queryFn:()=>api<{compute_device:string;cuda_available:boolean;detector:{name:string;status:string;tracker:string};plate:{status:string};modules:Array<{key:string;title:string;status:string}>}>('/models/status')});const h=health.data;return <><Header eyebrow="LOCAL RUNTIME" title="System health" description="Compute, models, storage, database, and processing readiness." actions={<button className="button secondary" onClick={()=>{health.refetch();models.refetch()}}><RefreshCw size={15}/> Refresh</button>}/><div className="metric-grid"><Metric label="Backend" value={h?.status??'Checking'} meta={h?.local_only?'Bound to localhost':'Exposure warning'} icon={HeartPulse} tone="green"/><Metric label="Compute" value={models.data?.cuda_available?'NVIDIA GPU':'CPU'} meta={models.data?.compute_device??'Detecting device'} icon={Zap}/><Metric label="Free disk" value={`${h?.disk_free_gb??'—'} GB`} meta="Evidence storage volume" icon={HardDrive} tone="amber"/><Metric label="Database" value={h?.database??'Checking'} meta="SQLite + WAL" icon={Database} tone="green"/></div><div className="dashboard-grid"><Card title="Runtime checks"><div className="health-list">{[['FFmpeg',h?.ffmpeg],['FFprobe',h?.ffprobe],['SQLite',h?.database==='connected'],['Local-only binding',h?.local_only],['CUDA acceleration',models.data?.cuda_available]].map(([label,ok])=><div key={String(label)}><span className={cx('status-dot',ok?'green':'amber')}/><span>{label}</span><strong>{ok?'Available':'Fallback active'}</strong></div>)}</div></Card><Card title="Model stack"><div className="model-stack"><div><Car size={18}/><span><strong>{models.data?.detector.name??'Loading'}</strong><small>Ultralytics · {models.data?.detector.tracker??'ByteTrack'}</small></span></div><div><FileSearch size={18}/><span><strong>FastALPR crop pipeline</strong><small>{models.data?.plate.status??'Loading status'}</small></span></div><div><AlertTriangle size={18}/><span><strong>Hazard extension interface</strong><small>Custom model needed for debris, fire, flooding, potholes</small></span></div></div></Card></div><Card title="Module capability status"><div className="module-status">{models.data?.modules.map(x=><div key={x.key}><span className="status-dot amber"/><div><strong>{x.title}</strong><span>{x.status}</span></div></div>)}</div></Card></>}

function SettingsPage(){
  const [ocr,setOcr]=useState(.65); const [det,setDet]=useState(.35); const [retention,setRetention]=useState(30)
  const [allowed,setAllowed]=useState('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'); const [minimum,setMinimum]=useState(4); const [maximum,setMaximum]=useState(12); const [regex,setRegex]=useState('')
  const save=useMutation({mutationFn:()=>api('/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({values:{ocr_confidence:ocr,detection_confidence:det,retention_days:retention,plate_allowed_characters:allowed,plate_minimum_length:minimum,plate_maximum_length:maximum,plate_regex:regex}})})})
  return <><Header eyebrow="SYSTEM POLICY" title="Settings" description="Confidence policy, retention, model paths, plate profiles, and operator safeguards." actions={<button className="button primary" onClick={()=>save.mutate()}><CheckCircle2 size={15}/> {save.isSuccess?'Saved':'Save settings'}</button>}/><div className="settings-layout"><Card title="Confidence thresholds"><label className="range-row"><span><strong>Object detection</strong><small>Minimum YOLO confidence</small></span><input type="range" min=".05" max=".95" step=".05" value={det} onChange={e=>setDet(+e.target.value)}/><b>{pct(det)}</b></label><label className="range-row"><span><strong>Plate OCR</strong><small>Below this: Insufficient confidence</small></span><input type="range" min=".2" max=".95" step=".05" value={ocr} onChange={e=>setOcr(+e.target.value)}/><b>{pct(ocr)}</b></label></Card><Card title="Generic plate profile"><div className="form-grid"><label>Profile name<input value="Generic Latin / digits" readOnly/></label><label>Allowed characters<input value={allowed} onChange={e=>setAllowed(e.target.value.toUpperCase())}/></label><label>Minimum length<input type="number" min="1" max="20" value={minimum} onChange={e=>setMinimum(+e.target.value)}/></label><label>Maximum length<input type="number" min="1" max="20" value={maximum} onChange={e=>setMaximum(+e.target.value)}/></label><label className="wide">Optional validation regex<input value={regex} onChange={e=>setRegex(e.target.value)} placeholder="Leave blank for country-agnostic matching"/></label></div><div className="notice compact"><AlertTriangle size={16}/><div><strong>Ethiopian profile is an editable placeholder</strong><span>No national format is invented or enforced without verified requirements and suitable training data.</span></div></div></Card><Card title="Privacy & retention"><label className="setting-row"><div><strong>Evidence retention</strong><span>Operator-controlled local cleanup period.</span></div><select value={retention} onChange={e=>setRetention(+e.target.value)}><option value="7">7 days</option><option value="30">30 days</option><option value="90">90 days</option><option value="365">1 year</option></select></label><label className="setting-row"><div><strong>Blur exports by default</strong><span>Prepare public portfolio exports without readable faces or plates.</span></div><input className="switch" type="checkbox" defaultChecked/></label></Card></div></>
}

function LiveMonitoring(){
  const client=useQueryClient(); const [name,setName]=useState(''); const [uri,setUri]=useState(''); const [sourceType,setSourceType]=useState('rtsp')
  const cameras=useQuery({queryKey:['cameras'],queryFn:()=>api<Array<{id:string;name:string;location:string;source_type:string;enabled:boolean;configured:boolean}>>('/cameras')})
  const add=useMutation({mutationFn:()=>api('/cameras',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,location:'Not specified',source_type:sourceType,source_uri:uri||null,enabled:true})}),onSuccess:()=>{setName('');setUri('');client.invalidateQueries({queryKey:['cameras']})}})
  return <><Header eyebrow="STREAM OPERATIONS" title="Live monitoring" description="Webcam, RTSP, and HTTP stream workspace for the later physical-camera phase."/><Card><div className="live-grid"><div className="live-view"><div><Radio size={36}/><strong>{cameras.data?.length?'Camera sources saved locally':'No live source configured'}</strong><span>Uploaded video analysis is validated first. Stream reconnect, latency, overlays, and capture activate when live ingestion is enabled for a saved source.</span><button className="button secondary" disabled><Play size={15}/> Connect stream</button></div><div className="live-toolbar"><button disabled><Pause size={16}/></button><span>FPS —</span><span>Latency —</span><span>Signal unknown</span></div></div><div className="live-side"><h3>Local camera source</h3><label>Name<input value={name} onChange={e=>setName(e.target.value)} placeholder="Intersection north"/></label><label>Type<select value={sourceType} onChange={e=>setSourceType(e.target.value)}><option value="rtsp">RTSP</option><option value="http">HTTP(S)</option><option value="webcam">Webcam</option></select></label><label>Stream URI<input type="password" value={uri} onChange={e=>setUri(e.target.value)} placeholder={sourceType==='webcam'?'Leave blank; index configured later':'Credentials stay local'}/></label><button className="button primary full" disabled={!name||add.isPending} onClick={()=>add.mutate()}>Save source</button><h3 className="overlay-title">Overlay layers</h3>{['Detections & track IDs','Estimated speed','Plate candidates','Zones and lines','Signal state','Active alerts'].map(x=><label key={x}><input type="checkbox" defaultChecked/>{x}</label>)}<div className="notice compact amber"><AlertTriangle size={16}/><div><strong>Upload pipeline first</strong><span>Live inference is intentionally disabled until camera reconnect and credential handling are validated.</span></div></div></div></div></Card></>
}

function App(){return <Shell><Routes><Route path="/" element={<Overview/>}/><Route path="/analysis" element={<VideoAnalysis/>}/><Route path="/live" element={<LiveMonitoring/>}/><Route path="/studio" element={<CameraStudio/>}/><Route path="/incidents" element={<IncidentReview/>}/><Route path="/analytics" element={<AnalyticsPage/>}/><Route path="/plates" element={<PlateSearch/>}/><Route path="/health" element={<SystemHealth/>}/><Route path="/settings" element={<SettingsPage/>}/></Routes></Shell>}
export default App
