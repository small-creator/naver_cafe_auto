import asyncio
import os
from playwright.async_api import async_playwright
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    message: str
    cookies: dict = None

async def connect_to_browserless():
    """Browserless 서비스에 연결"""
    browserless_url = os.getenv("BROWSERLESS_WS_URL")
    if not browserless_url:
        raise ValueError("BROWSERLESS_WS_URL 환경변수가 설정되지 않았습니다")
    
    playwright = await async_playwright().start()
    
    try:
        logger.info(f"Browserless 연결 시도: {browserless_url}")
        
        # 직접 연결 시도
        browser = await playwright.chromium.connect_over_cdp(browserless_url)
        logger.info(f"✅ Browserless 연결 성공!")
        return playwright, browser
        
    except Exception as e:
        logger.error(f"Browserless 연결 실패: {str(e)}")
        await playwright.stop()
        raise e

async def naver_login(username: str, password: str):
    """네이버 로그인 수행"""
    playwright = None
    browser = None
    
    try:
        playwright, browser = await connect_to_browserless()
        
        # 새 페이지 생성
        page = await browser.new_page()
        
        # 네이버 로그인 페이지로 이동
        await page.goto("https://nid.naver.com/nidlogin.login")
        
        # 페이지 로딩 대기
        await page.wait_for_load_state("networkidle")
        
        # 아이디 입력
        await page.fill("#id", username)
        await asyncio.sleep(1)
        
        # 비밀번호 입력
        await page.fill("#pw", password)
        await asyncio.sleep(1)
        
        # 로그인 버튼 클릭
        await page.click("#log\\.login")
        
        # 로그인 결과 대기 (최대 10초)
        try:
            # 로그인 성공 시 메인 페이지로 리다이렉트되거나 특정 요소가 나타남
            await page.wait_for_url("https://www.naver.com/", timeout=10000)
            
            # 쿠키 획득
            cookies = await page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            return LoginResponse(
                success=True,
                message="로그인 성공",
                cookies=cookie_dict
            )
            
        except Exception as e:
            # 로그인 실패 또는 추가 인증 필요
            current_url = page.url
            
            # 캡차나 추가 인증이 필요한 경우 체크
            if "captcha" in current_url or "verify" in current_url:
                return LoginResponse(
                    success=False,
                    message="캡차 또는 추가 인증이 필요합니다"
                )
            else:
                return LoginResponse(
                    success=False,
                    message="로그인에 실패했습니다. 아이디/비밀번호를 확인해주세요"
                )
    
    except Exception as e:
        logger.error(f"로그인 처리 중 오류 발생: {str(e)}")
        return LoginResponse(
            success=False,
            message=f"오류 발생: {str(e)}"
        )
    
    finally:
        # 리소스 정리
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()

@app.post("/login", response_model=LoginResponse)
async def login_endpoint(request: LoginRequest):
    """네이버 로그인 API 엔드포인트"""
    try:
        result = await naver_login(request.username, request.password)
        return result
    except Exception as e:
        logger.error(f"API 처리 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
