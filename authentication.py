from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext
import jwt
from dotenv import *
from fastapi import HTTPException, status
from models import User

config_credentials = dotenv_values(".env")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def get_password_hash(password):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


async def authenticate_user(username: str, password: str):
    user = await User.get(username=username)

    if user and verify_password(password, user.password):
        return user

    return False


async def token_generator(username: str, password: str):
    user = await authenticate_user(username, password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = {
        "id": user.id,
        "username": user.username
    }

    token = jwt.encode(token_data, config_credentials["SECRET2"])
    return token


async def verify_token(token: str):
    try:
        payload = jwt.decode(token, config_credentials["SECRET2"], algorithms=['HS256'])
        user = await User.get(id=payload.get('id'))
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def generate_reset_password_token(email: str):
    user = await User.get(email=email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email does not exist",
        )

    token_data = {
        "id": user.id,
        "email": user.email,
        "action": "reset_password"
    }

    token = jwt.encode(token_data, config_credentials["SECRET2"])

    return token


async def verify_pass_token(token: str):
    try:

        payload = jwt.decode(token, config_credentials["SECRET2"], algorithms=["HS256"])

        user_id = payload.get("id")

        user = await User.get(id=user_id)

        return user

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired token",
        )
    except InvalidTokenError:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid token",
        )
    except Exception as e:

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while verifying the token",
        )