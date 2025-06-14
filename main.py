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
        
        # CDP over WebSocket 연결
        browser = await playwright.chromium.connect_over_cdp(browserless_url)
        logger.info(f"✅ Browserless 연결 성공!")
        
        # 브라우저 상태 확인을 위해 컨텍스트 생성 테스트
        try:
            context = await browser.new_context()
            await context.close()
            logger.info("✅ 브라우저 컨텍스트 테스트 성공")
        except Exception as e:
            logger.warning(f"브라우저 컨텍스트 테스트 실패: {str(e)}")
        
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
        
        # 새 컨텍스트와 페이지 생성
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        logger.info("네이버 로그인 페이지로 이동 중...")
        
        # 네이버 로그인 페이지로 이동
        await page.goto("https://nid.naver.com/nidlogin.login", wait_until="networkidle")
        
        logger.info("로그인 폼 요소 찾는 중...")
        
        # 로그인 폼이 로드될 때까지 대기
        await page.wait_for_selector("#id", timeout=10000)
        await page.wait_for_selector("#pw", timeout=10000)
        
        # 아이디 입력
        logger.info("아이디 입력 중...")
        await page.fill("#id", username)
        await asyncio.sleep(1)
        
        # 비밀번호 입력
        logger.info("비밀번호 입력 중...")
        await page.fill("#pw", password)
        await asyncio.sleep(1)
        
        # 로그인 버튼 클릭
        logger.info("로그인 버튼 클릭...")
        await page.click("#log\\.login")
        
        # 로그인 결과 대기 (최대 15초)
        try:
            # 로그인 성공 시 메인 페이지로 리다이렉트되거나 특정 요소가 나타남
            await page.wait_for_url("https://www.naver.com/", timeout=15000)
            
            # 쿠키 획득
            cookies = await context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            logger.info("✅ 네이버 로그인 성공!")
            
            return LoginResponse(
                success=True,
                message="로그인 성공",
                cookies=cookie_dict
            )
            
        except Exception as e:
            # 로그인 실패 또는 추가 인증 필요
            current_url = page.url
            logger.warning(f"로그인 후 URL: {current_url}")
            
            # 캡차나 추가 인증이 필요한 경우 체크
            if "captcha" in current_url or "verify" in current_url:
                return LoginResponse(
                    success=False,
                    message="캡차 또는 추가 인증이 필요합니다"
                )
            elif "nidlogin.login" in current_url:
                return LoginResponse(
                    success=False,
                    message="로그인에 실패했습니다. 아이디/비밀번호를 확인해주세요"
                )
            else:
                # 다른 페이지로 이동했을 수 있음 (성공적일 수도 있음)
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                
                return LoginResponse(
                    success=True,
                    message="로그인 완료 (다른 페이지로 이동됨)",
                    cookies=cookie_dict
                )
    
    except Exception as e:
        logger.error(f"로그인 처리 중 오류 발생: {str(e)}")
        return LoginResponse(
            success=False,
            message=f"오류 발생: {str(e)}"
        )
    
    finally:
        # 리소스 정리
        try:
            if 'context' in locals():
                await context.close()
        except:
            pass
        
        if browser:
            try:
                await browser.close()
            except:
                pass
        
        if playwright:
            try:
                await playwright.stop()
            except:
                pass

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
