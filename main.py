from fastapi import FastAPI, Request,Query,Form,HTTPException
from fastapi.responses import HTMLResponse,RedirectResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token;
from google.auth.transport import requests
from google.cloud import firestore
import starlette.status as status
import json
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from datetime import datetime

app=FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
firebase_request_adapter = requests.Request()


firestore_db = firestore.Client(project="evproject-417219")

app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates") 




def getEV(user_token):

    ev = firestore_db.collection('ev_database').document(user_token['user_id'])

    if not ev.get().exists:
        ev_data = {
        "name":"",
        "manufacturer":"",
        "year":0,
        "battery_size":0,
        "wltp_range":0,
        "cost":0,
        "power":0,
        "rating":0,
        "review":"",
        "average_score":0,
        }
        firestore_db.collection("ev_database").document(user_token['user_id']).set(ev_data)
    return ev



def validateFirebaseToken(id_token):
    if not id_token:
        return None

    user_token = None
    try:
        user_token=google.oauth2.id_token.verify_firebase_token(id_token,firebase_request_adapter)   
    except ValueError as err:
        print(str(err))
    return user_token


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    id_token = request.cookies.get("token")
    user_token=None
    if id_token:
        try:
            user_token = validateFirebaseToken(id_token)
        except ValueError as err:
            print(str(err))
             
    print("2",user_token)
    collection_ref = firestore_db.collection('ev_database')
    docs = collection_ref.stream()
    all_records = []
    ev_data_with_ids = []
    

    for idx, doc in enumerate(docs, start=1):
        ev_data = doc.to_dict()
        ev_data['id'] = doc.id
        ev_data_with_ids.append(ev_data)
    return templates.TemplateResponse("allEv.html", {"request": request, "ev_data": ev_data_with_ids,"user_token":user_token})

@app.get("/login", response_class=HTMLResponse)
async def root(request: Request):

    id_token = request.cookies.get("token")
    error_message = "No error here"
    user_token = None

    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        except ValueError as err:
            print(str(err))

    return templates.TemplateResponse('login.html', {'request': request, 'user_token': user_token, 'error_message': error_message})            
    

@app.get("/add-ev",response_class=HTMLResponse)
async def updateForm(request:Request):
    return templates.TemplateResponse('addEv.html',{'request':request})

@app.post("/add-ev", response_class=RedirectResponse)
async def updateFormPost(request: Request):
    form = await request.form()
    ev_data = {
        "manufacturer": form['manufacturer'],
        "name": form['name'],
        "year": int(form['year']),
        "battery_size": float(form['batterySize']),
        "wltp_range": float(form['WLTPRange']),
        "cost": float(form['cost']),
        "power": float(form['power']),
       
    }

    

    ev_query = firestore_db.collection('ev_database') \
                           .where('manufacturer', '==', form['manufacturer']) \
                           .where('name', '==', form['name']) \
                           .where('year', '==', int(form['year'])) \
                           .limit(1) \
                           .stream()

    if len(list(ev_query)) > 0:
        message = "EV with the same name,year and manufacturer already exists."
        

        return templates.TemplateResponse("addEv.html", {"request": request, "message": message})

    
    ev_response = firestore_db.collection('ev_database').document() 
    ev_response.set(ev_data, merge=True)
    print("EV data",ev_data)
    return RedirectResponse("/",status_code=status.HTTP_302_FOUND)

@app.post("/update-ev/{ev_id}", response_class=RedirectResponse)
async def update_ev(request:Request,ev_id: str):
    form = await request.form() 
    try:
        ev_data = {
        "manufacturer": form['manufacturer'],
        "name": form['name'],
        "year": int(form['year']),
        "battery_size": float(form['battery_size']),
        "wltp_range": float(form['wltp_range']),
        "cost": float(form['cost']),
        "power": float(form['power']),
        }
        
        
        ev_ref = firestore_db.collection('ev_database').document(ev_id)
        ev_doc = ev_ref.get()
        if not ev_doc.exists:
            raise HTTPException(status_code=404, detail="EV not found")

        
        ev_ref.update(ev_data)

        return RedirectResponse("/",status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
       
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/query/{ev_id}")
def delete_ev(request:Request,ev_id: str):
    print("1")
    doc_ref = firestore_db.collection('ev_database').document(ev_id)
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail="EV not found")
    doc_ref.delete()
    message = "EV deleted successfully"

    return RedirectResponse("/",status_code=status.HTTP_302_FOUND)

@app.post("/filter-query")
async def search(request: Request,attribute: str = Form(None), value: str = Form(None), minValue: int = Form(None), maxValue: int = Form(None)):
    
    if value is not None:
        query = firestore_db.collection("ev_database").where(attribute, "==", value)
    elif minValue is not None and maxValue is not None:
        query = firestore_db.collection("ev_database").where(attribute, ">=", minValue).where(attribute, "<=", maxValue)
    else:
        return RedirectResponse("/",status_code=status.HTTP_302_FOUND)
    results = query.stream()
    evs = [{'id': ev.id, **ev.to_dict()} for ev in results]
    return templates.TemplateResponse("allEv.html", {"request": request, "search_results": evs,"attribute": attribute, "value": value, "minValue": minValue, "maxValue": maxValue})

@app.get("/ev/{ev_id}", response_class=HTMLResponse)
async def ev_info(request: Request, ev_id: str):     
    id_token = request.cookies.get("token")
    error_message = "No error here"
    user_token = None
    if id_token:
        try:
            user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
        except ValueError as err:
            print(str(err))

    ev_reviews = firestore_db.collection(f'ev_database/{ev_id}/reviews').stream()
   
    reviews_data = [review.to_dict() for review in ev_reviews]
    reviews_with_timestamp = [review for review in reviews_data if "timestamp" in review]
    if reviews_with_timestamp:
        sorted_reviews = sorted(reviews_with_timestamp, key=lambda x: x["timestamp"], reverse=True)
    else:
        sorted_reviews = []
    total_score = 0
    total_reviews = 0
    
    for review in reviews_data:
        if "rating" in review:  
            total_score += review["rating"]
            total_reviews += 1

    if total_reviews == 0:
        average_score = 0
    else:
        average_score = total_score / total_reviews
    ev = firestore_db.collection('ev_database').document(ev_id).get()
    ev_data = ev.to_dict()
    ev_data['id'] = ev_id
    print("ev_data",ev_data)
    if ev_data is None:
        return {"message": "EV not found"}
    return templates.TemplateResponse("evInfo.html", {"request": request, "evData": ev_data,"average_score":average_score,"reviews_data":sorted_reviews,"user_token":user_token})
   
def get_ev_data(ev_id):
    ev_reviews = firestore_db.collection(f'ev_database/{ev_id}/reviews').stream()
   
    reviews_data = [review.to_dict() for review in ev_reviews]
    
    total_score = 0
    total_reviews = 0
    
    for review in reviews_data:
        if "rating" in review:  
            total_score += review["rating"]
            total_reviews += 1

    if total_reviews == 0:
        average_score = 0
    else:
        average_score = total_score / total_reviews

    doc_ref = firestore_db.collection('ev_database').document(ev_id).get()
    
    if doc_ref.exists:
        ev_data = doc_ref.to_dict()
        ev_data['id'] = ev_id
        ev_data['rating'] = average_score
        return ev_data
    else:
        return None

@app.post("/compare", response_class=HTMLResponse)
async def compare(request: Request, ev1: str = Form(...), ev2: str = Form(...)):
    
    print("EV1",ev1)
    print("EV2",ev2)
    ev1_data = get_ev_data(ev1)
    ev2_data = get_ev_data(ev2)
    response_data = {"ev1": ev1_data, "ev2": ev2_data}
    return templates.TemplateResponse("compareEv.html", {"request": request, "evData": response_data})


# @app.get("/ev-info", response_class=HTMLResponse)
# async def ev_info(request: Request):
    
#     return templates.TemplateResponse("evInfo.html", {"request": request, "evData": ev_data})



class Review(BaseModel):
    rating: int
    review: str

@app.post("/ev_info/{ev_id}/reviews/")
async def submit_review(request: Request,ev_id: str, rating: int = Form(...), review: str = Form(None)):
    
    try:    
        
        reviews_ref = firestore_db.collection(f'ev_database/{ev_id}/reviews')

        new_review_ref = reviews_ref.add({
            "rating": rating,
            "review": review,
            "timestamp":datetime.now()
            })
        return RedirectResponse("/",status_code=status.HTTP_302_FOUND)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


