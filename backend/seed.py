from datetime import date, timedelta
from app.database import Base, engine, SessionLocal
from app.models.subscription import Subscription, PriceHistory, CancellationRecord

Base.metadata.create_all(bind=engine)
db=SessionLocal()
if db.query(Subscription).count()>0 and db.query(Subscription).filter(Subscription.currency=="INR").count()>0:
    # Replace the prior INR-only demo set with the US-focused sample set.
    db.query(CancellationRecord).delete(synchronize_session=False)
    db.query(PriceHistory).delete(synchronize_session=False)
    db.query(Subscription).delete(synchronize_session=False)
    db.commit()
elif db.query(Subscription).count()>0:
    # Existing demo installations can rerun seed to get a consistent USD sample.
    db.query(CancellationRecord).delete(synchronize_session=False)
    db.query(PriceHistory).delete(synchronize_session=False)
    db.query(Subscription).delete(synchronize_session=False)
    db.commit()
if db.query(Subscription).count()==0:
    today=date.today()
    rows=[
        ("Netflix","Netflix","Entertainment",15.49,"monthly",4,"often",None),
        ("Spotify Premium","Spotify","Entertainment",11.99,"monthly",8,"often",None),
        ("Adobe Creative Cloud","Adobe","Software",59.99,"monthly",12,"often",None),
        ("Google One","Google","Cloud storage",2.99,"monthly",15,"often",None),
        ("Notion Plus","Notion","Productivity",10.00,"monthly",18,"often",None),
        ("ChatGPT Plus","OpenAI","AI tools",20.00,"monthly",21,"often",None),
        ("Duolingo Super","Duolingo","Education",83.99,"yearly",25,"rarely",None),
        ("FitPass","FitPass","Fitness",29.99,"monthly",29,"never",None),
        ("iCloud+","Apple","Cloud storage",0.99,"monthly",33,"often",None),
        ("Amazon Prime","Amazon","Shopping",139.00,"yearly",40,"often",None),
        ("Figma Professional","Figma","Software",16.00,"monthly",46,"unknown",None),
        ("Headspace","Headspace","Fitness",12.99,"monthly",54,"rarely",(9.99,12.99)),
        ("Prime Video Channels","Amazon","Entertainment",8.99,"monthly",60,"never",None),
        ("Old VPN Plan","SecureNet","Software",0,"monthly",0,"never",None),
    ]
    for i,(name,merchant,category,price,interval,days,usage,hike) in enumerate(rows):
        canceled=price==0
        s=Subscription(name=name,merchant=merchant,category=category,price=price or 5.99,currency="USD",billing_interval=interval,next_billing_date=today+timedelta(days=days) if days else None,start_date=today-timedelta(days=365-i*13),status="canceled" if canceled else "active",payment_method=["Visa •• 4242","Mastercard •• 1008","PayPal Sandbox"][i%3],website=f"https://www.{merchant.lower().replace(' ','')}.com",cancellation_url=None,notes="Illustrative demo record; values are simulated.",usage_frequency=usage)
        if hike: s.prices.append(PriceHistory(old_price=hike[0],new_price=hike[1],currency="USD",change_date=__import__('datetime').datetime.combine(today-timedelta(days=27), __import__('datetime').datetime.min.time())))
        db.add(s)
    db.commit()
db.close()
print("Demo subscriptions are ready.")
