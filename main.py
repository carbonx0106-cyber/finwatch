from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, selectinload
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, DateTime, ForeignKey, select, func, or_
from contextlib import asynccontextmanager
import httpx, os, logging
from datetime import datetime

# ── DB setup ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./finwatch.db")
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()

class Official(Base):
    __tablename__ = "officials"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, index=True)
    initials = Column(String)
    role = Column(String)
    state = Column(String, index=True)
    ministry = Column(String)
    party = Column(String)
    declared_assets_cr = Column(Float, default=0)
    unexplained_wealth_cr = Column(Float, default=0)
    risk_score = Column(Integer, default=0)
    risk_level = Column(String, default="Low")
    pan_partial = Column(String)
    ec_affidavit_url = Column(String)
    myneta_id = Column(String)
    source = Column(String)
    last_synced = Column(DateTime, default=datetime.utcnow)
    companies = relationship("Company", back_populates="official", cascade="all, delete-orphan")
    asset_history = relationship("AssetHistory", back_populates="official", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="official", cascade="all, delete-orphan")
    events = relationship("FlaggedEvent", back_populates="official", cascade="all, delete-orphan")

class Company(Base):
    __tablename__ = "companies"
    id = Column(Integer, primary_key=True)
    official_id = Column(Integer, ForeignKey("officials.id"))
    name = Column(String)
    cin = Column(String)
    link_type = Column(String)
    turnover_cr = Column(Float, default=0)
    gst_filed = Column(Boolean, default=False)
    it_filed = Column(Boolean, default=False)
    official = relationship("Official", back_populates="companies")

class AssetHistory(Base):
    __tablename__ = "asset_history"
    id = Column(Integer, primary_key=True)
    official_id = Column(Integer, ForeignKey("officials.id"))
    year = Column(Integer)
    declared_cr = Column(Float)
    estimated_cr = Column(Float)
    official = relationship("Official", back_populates="asset_history")

class Property(Base):
    __tablename__ = "properties"
    id = Column(Integer, primary_key=True)
    official_id = Column(Integer, ForeignKey("officials.id"))
    description = Column(String)
    registrant = Column(String)
    value_cr = Column(Float)
    date = Column(String)
    flag = Column(String)
    official = relationship("Official", back_populates="properties")

class FlaggedEvent(Base):
    __tablename__ = "flagged_events"
    id = Column(Integer, primary_key=True)
    official_id = Column(Integer, ForeignKey("officials.id"))
    date = Column(String)
    event = Column(Text)
    severity = Column(String)
    source = Column(String)
    official = relationship("Official", back_populates="events")

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# ── App ───────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

async def seed():
    async with AsyncSessionLocal() as db:
        if (await db.execute(select(func.count(Official.id)))).scalar() > 0:
            return
        demo = [
            {"name":"Official A (Demo)","initials":"OA","role":"MP, Lok Sabha","state":"State X","ministry":"Finance Committee","party":"Party X","declared_assets_cr":4.2,"unexplained_wealth_cr":18.7,"risk_score":92,"risk_level":"Critical","pan_partial":"XXXXX0000X","ec_affidavit_url":"https://myneta.info","myneta_id":"demo_001","source":"demo",
             "cos":[{"name":"Demo Realty Pvt Ltd","cin":"U70100XX2018PTC000001","link_type":"Director (spouse)","turnover_cr":4.2,"gst_filed":False,"it_filed":False}],
             "hist":[(2019,1.2,2.1),(2020,1.8,5.4),(2021,2.3,9.2),(2022,2.9,12.8),(2023,3.6,16.1),(2024,4.2,22.9)],
             "evs":[{"date":"Dec 2024","event":"Property registration anomaly detected in public records","severity":"Critical","source":"Sub-Registrar"}],
             "props":[{"description":"4BHK Metro City","registrant":"Spouse (Demo)","value_cr":3.8,"date":"Oct 2024","flag":"Benami?"}]},
            {"name":"Official B (Demo)","initials":"OB","role":"MLA","state":"State Y","ministry":"Public Works","party":"Party Y","declared_assets_cr":2.8,"unexplained_wealth_cr":11.2,"risk_score":78,"risk_level":"High","pan_partial":"YYYYY1111Y","ec_affidavit_url":"https://myneta.info","myneta_id":"demo_002","source":"demo",
             "cos":[{"name":"Demo Infra Pvt Ltd","cin":"U45200YY2019PTC000002","link_type":"Director","turnover_cr":6.2,"gst_filed":False,"it_filed":False}],
             "hist":[(2019,0.8,1.5),(2020,1.1,3.2),(2021,1.5,5.1),(2022,1.9,7.8),(2023,2.3,10.2),(2024,2.8,14.0)],
             "evs":[{"date":"Oct 2024","event":"Linked company wins govt contract from own ministry committee","severity":"High","source":"GEM Portal"}],
             "props":[]},
        ]
        for od in demo:
            o = Official(**{k:v for k,v in od.items() if k not in ["cos","hist","evs","props"]})
            db.add(o); await db.flush()
            for c in od["cos"]: db.add(Company(official_id=o.id,**c))
            for y,d,e in od["hist"]: db.add(AssetHistory(official_id=o.id,year=y,declared_cr=d,estimated_cr=e))
            for ev in od["evs"]: db.add(FlaggedEvent(official_id=o.id,**ev))
            for p in od["props"]: db.add(Property(official_id=o.id,**p))
        await db.commit()
        logger.info("Demo data seeded")

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed()
    yield

app = FastAPI(title="FinWatch India API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

def o2d(o, full=False):
    d = {"id":o.id,"name":o.name,"initials":o.initials or "","role":o.role,"state":o.state,"ministry":o.ministry,"party":o.party or "","declared_assets_cr":o.declared_assets_cr,"unexplained_wealth_cr":o.unexplained_wealth_cr,"linked_companies":len(o.companies) if o.companies else 0,"risk_score":o.risk_score,"risk_level":o.risk_level,"pan_partial":o.pan_partial,"ec_affidavit_url":o.ec_affidavit_url,"source":o.source,"last_synced":o.last_synced.isoformat() if o.last_synced else None}
    if full:
        d["companies"]=[{"id":c.id,"name":c.name,"cin":c.cin,"link_type":c.link_type,"turnover_cr":c.turnover_cr,"gst_filed":c.gst_filed,"it_filed":c.it_filed} for c in (o.companies or [])]
        d["asset_history"]=[{"year":h.year,"declared":h.declared_cr,"estimated":h.estimated_cr} for h in sorted(o.asset_history or [],key=lambda x:x.year)]
        d["properties"]=[{"id":p.id,"description":p.description,"registrant":p.registrant,"value_cr":p.value_cr,"date":p.date,"flag":p.flag} for p in (o.properties or [])]
        d["flagged_events"]=[{"id":e.id,"date":e.date,"event":e.event,"severity":e.severity,"source":e.source} for e in (o.events or [])]
    return d

class AIRequest(BaseModel):
    query: str
    entity_id: Optional[int] = None

@app.get("/api/stats")
async def stats(db: AsyncSession = Depends(get_db)):
    total=(await db.execute(select(func.count(Official.id)))).scalar()
    critical=(await db.execute(select(func.count(Official.id)).where(Official.risk_level=="Critical"))).scalar()
    high=(await db.execute(select(func.count(Official.id)).where(Official.risk_level=="High"))).scalar()
    companies=(await db.execute(select(func.count(Company.id)))).scalar()
    unexplained=(await db.execute(select(func.sum(Official.unexplained_wealth_cr)))).scalar() or 0
    return {"officials_tracked":total,"critical_risk":critical,"high_risk":high,"shell_companies":companies,"total_unexplained_cr":round(float(unexplained),1),"anomalies_detected":critical+high,"states_covered":8,"last_updated":datetime.utcnow().isoformat()}

@app.get("/api/officials")
async def list_officials(risk:Optional[str]=None,state:Optional[str]=None,search:Optional[str]=None,sort:str="risk_score",page:int=1,limit:int=20,db:AsyncSession=Depends(get_db)):
    q=select(Official).options(selectinload(Official.companies))
    if risk: q=q.where(Official.risk_level==risk)
    if state: q=q.where(Official.state==state)
    if search: q=q.where(or_(Official.name.ilike(f"%{search}%"),Official.ministry.ilike(f"%{search}%")))
    if sort=="unexplained_wealth_cr": q=q.order_by(Official.unexplained_wealth_cr.desc())
    else: q=q.order_by(Official.risk_score.desc())
    total=(await db.execute(select(func.count()).select_from(q.subquery()))).scalar()
    result=await db.execute(q.offset((page-1)*limit).limit(limit))
    return {"total":total,"page":page,"limit":limit,"results":[o2d(o) for o in result.scalars().all()]}

@app.get("/api/officials/{oid}")
async def get_official(oid:int,db:AsyncSession=Depends(get_db)):
    q=select(Official).where(Official.id==oid).options(selectinload(Official.companies),selectinload(Official.asset_history),selectinload(Official.properties),selectinload(Official.events))
    o=(await db.execute(q)).scalar_one_or_none()
    if not o: raise HTTPException(404,"Not found")
    return o2d(o,full=True)

@app.get("/api/leaderboard")
async def leaderboard(db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(Official).order_by(Official.risk_score.desc()).limit(50))
    return [{"rank":i+1,"id":o.id,"name":o.name,"role":o.role,"state":o.state,"risk_score":o.risk_score,"risk_level":o.risk_level,"unexplained_cr":o.unexplained_wealth_cr} for i,o in enumerate(result.scalars().all())]

@app.get("/api/properties/flagged")
async def flagged_props(db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(Property).options(selectinload(Property.official)))
    props=result.scalars().all()
    return {"total":len(props),"properties":[{"id":p.id,"description":p.description,"registrant":p.registrant,"value_cr":p.value_cr,"date":p.date,"flag":p.flag,"official":p.official.name,"official_id":p.official_id,"role":p.official.role} for p in props]}

@app.get("/api/network")
async def network(db:AsyncSession=Depends(get_db)):
    result=await db.execute(select(Official).options(selectinload(Official.companies)))
    officials=result.scalars().all()
    nodes,edges=[],[]
    for o in officials:
        nodes.append({"id":f"off_{o.id}","label":o.name,"type":"official","risk":o.risk_level})
        for c in o.companies:
            nodes.append({"id":f"co_{c.id}","label":c.name,"type":"company","cin":c.cin})
            edges.append({"source":f"off_{o.id}","target":f"co_{c.id}","label":c.link_type})
    return {"nodes":nodes,"edges":edges}

@app.get("/api/search")
async def search(q:str=Query(...,min_length=2),db:AsyncSession=Depends(get_db)):
    stmt=select(Official).where(or_(Official.name.ilike(f"%{q}%"),Official.ministry.ilike(f"%{q}%"),Official.state.ilike(f"%{q}%"))).limit(10)
    result=await db.execute(stmt)
    return {"query":q,"results":[{"type":"official","id":o.id,"name":o.name,"subtitle":f"{o.role} — {o.state}","risk":o.risk_level} for o in result.scalars().all()]}

@app.get("/api/sources")
async def sources():
    return {"sources":[
        {"name":"ECI Affidavit Portal (Myneta)","url":"https://myneta.info","status":"active","description":"Election declarations for all elected officials"},
        {"name":"MCA21 — ROC Database","url":"https://www.mca.gov.in","status":"active","description":"Company directors, shareholding, financials"},
        {"name":"eCourts API","url":"https://ecourts.gov.in","status":"active","description":"FIR data, charge sheets, judicial orders"},
        {"name":"DILRMP Land Records","url":"https://dilrmp.gov.in","status":"partial","description":"State-wise land registry"},
        {"name":"Parliamentary Debates","url":"https://sansad.in","status":"active","description":"Lok Sabha / Rajya Sabha transcripts"},
        {"name":"RERA Filings","url":"https://rera.gov.in","status":"active","description":"Real estate registrations"},
        {"name":"GEM / e-Tender Portal","url":"https://gem.gov.in","status":"active","description":"Government procurement contracts"},
        {"name":"ED / PMLA Attachments","url":"https://enforcementdirectorate.gov.in","status":"manual","description":"Press releases and gazette notifications"},
    ]}

@app.post("/api/ai/analyse")
async def ai_analyse(req:AIRequest,db:AsyncSession=Depends(get_db)):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(500,"ANTHROPIC_API_KEY not configured")
    context=""
    if req.entity_id:
        q=select(Official).where(Official.id==req.entity_id).options(selectinload(Official.companies),selectinload(Official.events))
        o=(await db.execute(q)).scalar_one_or_none()
        if o:
            cos="; ".join([f"{c.name} ({c.link_type}, ₹{c.turnover_cr}Cr, GST:{c.gst_filed})" for c in o.companies])
            context=f"\nOfficial: {o.name}\nRole: {o.role}, {o.ministry}, {o.state}\nDeclared: ₹{o.declared_assets_cr} Cr\nUnexplained: ₹{o.unexplained_wealth_cr} Cr\nRisk: {o.risk_score}/100 ({o.risk_level})\nCompanies: {cos}\n"
    system="You are a senior anti-corruption financial intelligence analyst at a civil society watchdog in India. Use ₹ for amounts. Plain text only, no markdown. Be analytical and factual. Cite data sources. End with recommended RTI/journalist next steps."
    async with httpx.AsyncClient(timeout=30) as client:
        r=await client.post("https://api.anthropic.com/v1/messages",
            headers={"x-api-key":ANTHROPIC_API_KEY,"anthropic-version":"2023-06-01"},
            json={"model":"claude-opus-4-6","max_tokens":1500,"system":system,"messages":[{"role":"user","content":f"{context}\nQuery: {req.query}"}]})
        if r.status_code!=200: raise HTTPException(502,"AI error")
        return {"analysis":r.json()["content"][0]["text"],"entity_id":req.entity_id,"timestamp":datetime.utcnow().isoformat()}
