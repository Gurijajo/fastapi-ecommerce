import secrets
from fastapi.responses import RedirectResponse
from typing import Optional, Type
from PIL import Image
from fastapi import Depends, File, UploadFile, FastAPI
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from tortoise import BaseDBAsyncClient
from tortoise.contrib.fastapi import register_tortoise
from tortoise.signals import post_save
from dotenv import *
from authentication import *
from email_utils import *
from models import *
config_credentials = dotenv_values(".env")

app = FastAPI()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

app.mount("/static", StaticFiles(directory="static"), name="static")

oath2_scheme = OAuth2PasswordBearer(tokenUrl = 'token')

@app.post('/token')
async def generate_token(request_form: OAuth2PasswordRequestForm = Depends()):
    token = await token_generator(request_form.username, request_form.password)
    return {'access_token' : token, 'token_type' : 'bearer'}



async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, config_credentials["SECRET2"], algorithms=["HS256"])
        user = await User.get(id=payload.get("id"))

    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


@app.post('/user/me')
async def user_login(user: user_pydanticIn = Depends(get_current_user)):
    business = await Business.get(owner=user)
    logo = business.logo
    logo_path = "localhost:8000/static/images" + logo
    return {
        "status": "success",
        "data": {
            "username": user.username,
            "email": user.email,
            "verified": user.is_verified,
            "joined_date": user.join_date.strftime("%m/%d/%Y"),
            "logo": logo_path
        }
    }


@post_save(User)
async def create_business(
        sender: Type[User],
        instance: User,
        created: bool,
        using_db: Optional[BaseDBAsyncClient],
        update_fields: Optional[list[str]]
) -> None:
    if created:
        business_obj = await Business.create(
            business_name=instance.username, owner=instance)
        await business_pydantic.from_tortoise_orm(business_obj)
        # send email functionality
        await send_verification_email([instance.email], instance)


@app.post("/registration")
async def user_registration(user: user_pydanticIn):
    user_info = user.dict(exclude_unset=True)
    user_info["password"] = get_password_hash(user_info["password"])
    user_obj = await User.create(**user_info)
    new_user = await user_pydantic.from_tortoise_orm(user_obj)
    return {
        "status": "ok",
        "data": f"Hello {new_user.username}!"
    }


templates = Jinja2Templates(directory="templates")


@app.get('/verification', response_class=HTMLResponse)
async def email_verification(request: Request, token: str):
    user = await verify_token(token)
    if user and not user.is_verified:
        user.is_verified = True
        await user.save()
        return templates.TemplateResponse("verification.html",
                                          {"request": request, "username": user.username}
                                          )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/")
def index():
    return RedirectResponse(url="/docs")

@app.post("/uploadfile/profile")
async def create_upload_file(file: UploadFile = File(...), user: user_pydanticIn = Depends(get_current_user)):
    filepath = "./static/images/"
    filename = file.filename
    extension = filename.split(".")[1]

    if extension not in ["png", "jpg", "jpeg"]:
        return {"status": "error", "detail": "File extension not supported"}

    token_name = secrets.token_hex(10) + "." + extension
    generate_name = filepath + token_name
    file_content = await file.read()

    with open(generate_name, "wb") as f:
        f.write(file_content)

    img = Image.open(generate_name)
    img = img.resize(size=(200, 200))
    img.save(generate_name)

    f.close()

    business = await Business.get(owner=user)
    owner = await business.owner

    if owner == user:
        business.logo = token_name
        await business.save()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )
    file_url = "localhost:8000" + generate_name[1:]
    return {"status": "success", "filename": file_url}


@app.post("/uploadfile/product/{id}")
async def create_upload_file(id: int, file: UploadFile = File(...), user: user_pydanticIn = Depends(get_current_user)):
    filepath_products = "./static/products/"
    filename_products = file.filename
    extension = filename_products.split(".")[1]

    if extension not in ["png", "jpg", "jpeg"]:
        return {"status": "error", "detail": "File extension not supported"}

    token_name = secrets.token_hex(10) + "." + extension
    generate_name = filepath_products + token_name
    file_content = await file.read()

    with open(generate_name, "wb") as f:
        f.write(file_content)

    img = Image.open(generate_name)
    img = img.resize(size=(200, 200))
    img.save(generate_name)

    f.close()

    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner

    if owner == user:
        product.product_image = token_name
        await product.save()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )
    file_url = "localhost:8000" + generate_name[1:]
    return {"status": "success", "filename": file_url}


@app.post("/products")
async def create_product(product: product_pydanticIn, user: user_pydanticIn = Depends(get_current_user)):
    product = product.dict(exclude_unset=True)

    if product["original_price"] > 0:
        product["percentage_discount"] = ((product["original_price"] - product["new_price"]) / product[
            "original_price"]) * 100

        product_obj = await Product.create(**product, business=user)
        product_obj = await product_pydantic.from_tortoise_orm(product_obj)

        return {"status": "success", "data": product_obj}
    else:
        return {"status": "error"}


@app.get("/product")
async def get_product():
    response = await product_pydantic.from_queryset(Product.all())
    return {"status": "success", "data": response}


@app.get("/product/{id}")
async def get_product(id: int):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner
    response = await product_pydantic.from_queryset_single(Product.get(id=id))
    return {"status": "success",
            "data": {
                "product_details": response,
                "business_details": {
                    "name": business.business_name,
                    "city": business.city,
                    "region": business.region,
                    "description": business.business_description,
                    "logo": business.logo,
                    "owner_id": owner.id,
                    "email": owner.email,
                    "join_date": owner.join_date.strftime("%d/%m/%Y")
                }
            }
            }


@app.delete("/product/{id}")
async def delete_product(
        id: int, user: user_pydantic = Depends(get_current_user)
):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner

    if user.id == owner.id:
        await product.delete()
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"status": "Success"}


@app.put("/product/{id}")
async def update_product(id: int, update_info: product_pydanticIn, user: user_pydanticIn = Depends(get_current_user)):
    product = await Product.get(id=id)
    business = await product.business
    owner = await business.owner

    update_info = update_info.dict(exclude_unset=True)
    update_info["date_publioshed"] = datetime.utcnow()

    if user == owner and update_info["original_price"] > 0:
        update_info["percentage_discount"] = ((update_info["original_price"] - update_info["new_price"]) / update_info[
            "original_price"]) * 100
        product = await product.update_from_dict(update_info)
        await product.save()
        response = product_pydantic.from_orm(product)
        return {"status": "success", "data": response}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.put("/business/{id}")
async def update_business(id: int, update_business: business_pydanticIn,
                          user: user_pydanticIn = Depends(get_current_user)):
    update_business = update_business.dict(exclude_unset=True)
    business = await Business.get(id=id)
    business_owner = await business.owner

    if user == business_owner:
        await business.update_from_dict(update_business)
        await business.save()
        response = await business_pydantic.from_tortoise_orm(business)

        return {"status": "success", "data": response}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.delete("/business/{id}")
async def delete_business(id: int, user: user_pydanticIn = Depends(get_current_user)):
    business = await Business.get(id=id)
    owner = await business.owner

    if user == owner:
        await business.delete()
        return {"status": "Success"}
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated to perform this action",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.post("/forgot-password")
async def forgot_password(email: str):
    user = await User.get(email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist",
        )

    await send_password_reset([email], user)
    return {"message": "Password reset email sent"}

@app.post("/reset-password", response_model=dict)
async def reset_password(token: str, new_password: str):
    user = await verify_pass_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    user.password = get_password_hash(new_password)
    await user.save()
    return {"message": "Password reset successfully"}

@app.get('/reset-password', response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    user = await verify_pass_token(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )

    return templates.TemplateResponse("reset_password.html", {"request": request, "token": token})

register_tortoise(
    app,
    db_url="sqlite://database.sqlite3",
    modules={"models": ["models"]},
    generate_schemas=True,
    add_exception_handlers=True
)
