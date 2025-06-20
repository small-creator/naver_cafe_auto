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
        
        # WebSocket URL을 HTTP URL로 변환하여 다른 방식으로 연결 시도
        if browserless_url.startswith('wss://'):
            # WebSocket URL을 HTTP로 변환
            http_url = browserless_url.replace('wss://', 'https://').replace('/playwright', '')
            
            # 다양한 연결 방식 시도
            connection_options = [
                # 원본 WebSocket 연결
                browserless_url,
                # HTTP 기반 연결
                f"{http_url}/json/version",
                # 다른 엔드포인트들
                browserless_url.replace('/playwright', '/chromium'),
                browserless_url.replace('?token=', '/websocket?token='),
            ]
        else:
            connection_options = [browserless_url]
        
        last_error = None
        for url in connection_options:
            try:
                logger.info(f"연결 시도 중: {url}")
                
                # 간단한 브라우저 연결 시도
                browser = await playwright.chromium.connect_over_cdp(url)
                
                # 연결 후 간단한 테스트
                try:
                    # 브라우저 정보 대신 페이지 생성으로 테스트
                    page = await browser.new_page()
                    await page.close()
                    logger.info(f"✅ Browserless 연결 및 테스트 성공: {url}")
                    return playwright, browser
                except Exception as test_error:
                    logger.warning(f"브라우저 테스트 실패: {str(test_error)}")
                    # 테스트 실패해도 브라우저 객체는 반환 (사용 가능할 수 있음)
                    logger.info(f"✅ Browserless 기본 연결 성공: {url}")
                    return playwright, browser
                
            except Exception as e:
                logger.warning(f"❌ 연결 실패 ({url}): {str(e)}")
                last_error = e
                try:
                    if 'browser' in locals():
                        await browser.close()
                except:
                    pass
                continue
        
        # 모든 연결 시도 실패
        raise last_error or Exception("모든 연결 시도 실패")
        
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
        
        # 새 컨텍스트와 페이지 생성 (봇 탐지 회피)
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='ko-KR',
            timezone_id='Asia/Seoul',
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                'Sec-Ch-Ua-Mobile': '?0',
                'Sec-Ch-Ua-Platform': '"Windows"',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            },
            # 자바스크립트 활성화 및 이미지 로드
            java_script_enabled=True,
        )
        page = await context.new_page()
        
        logger.info("네이버 로그인 페이지로 이동 중...")
        
        # 먼저 네이버 메인 페이지 방문 (자연스러운 사용자 행동)
        await page.goto("https://www.naver.com", wait_until="networkidle")
        await asyncio.sleep(2)
        
        # 그 다음 로그인 페이지로 이동
        await page.goto("https://nid.naver.com/nidlogin.login", wait_until="networkidle")
        
        # 페이지 로드 후 잠시 대기 (자연스러운 사용자 행동)
        await asyncio.sleep(3)
        
        logger.info("로그인 폼 요소 찾는 중...")
        
        # 로그인 폼이 로드될 때까지 대기
        logger.info("로그인 폼 요소 찾는 중...")
        
        # 로그인 폼 대기
        await page.wait_for_selector("#frmNIDLogin", timeout=10000)
        
        # 아이디 입력 (완전히 새로운 방식)
        logger.info("아이디 입력 중...")
        await page.wait_for_selector("#id", timeout=5000)
        
        # 자연스러운 마우스 움직임
        await page.mouse.move(100, 100)
        await asyncio.sleep(0.5)
        await page.mouse.move(500, 300)
        await asyncio.sleep(0.3)
        
        # 1. 필드 포커스
        await page.focus("#id")
        await asyncio.sleep(1)
        
        # 2. 기존 값 완전 삭제
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        await asyncio.sleep(0.8)
        
        # 3. 실제 사람처럼 천천히 타이핑 (각 문자마다 랜덤 지연)
        for i, char in enumerate(username):
            await page.keyboard.type(char)
            # 랜덤 지연 (200-500ms) - 더 느리게
            import random
            delay = random.randint(200, 500)
            await asyncio.sleep(delay / 1000)
        
        # 4. Tab 키로 다음 필드로 이동 (자연스러운 사용자 행동)
        await asyncio.sleep(1.5)
        
        # 입력값 확인
        id_value = await page.input_value("#id")
        logger.info(f"아이디 입력 확인: '{id_value}' (길이: {len(id_value)})")
        
        # 비밀번호 입력 (완전히 새로운 방식)
        logger.info("비밀번호 입력 중...")
        
        # 자연스러운 마우스 움직임
        await page.mouse.move(300, 400)
        await asyncio.sleep(0.4)
        
        # 1. Tab 키로 비밀번호 필드로 이동하거나 직접 포커스
        await page.keyboard.press("Tab")
        await asyncio.sleep(1)
        
        # 또는 직접 포커스
        await page.focus("#pw")
        await asyncio.sleep(0.8)
        
        # 2. 기존 값 완전 삭제
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        await asyncio.sleep(0.8)
        
        # 3. 실제 사람처럼 천천히 타이핑
        for i, char in enumerate(password):
            await page.keyboard.type(char)
            # 랜덤 지연 (200-500ms) - 더 느리게
            delay = random.randint(200, 500)
            await asyncio.sleep(delay / 1000)
        
        # 입력값 확인 (비밀번호는 보안상 길이만)
        pw_value = await page.input_value("#pw")
        logger.info(f"비밀번호 입력 확인: 길이 {len(pw_value)}")
        
        # 입력 완료 후 더 오래 대기
        await asyncio.sleep(5)
        
        # 로그인 버튼 클릭
        logger.info("로그인 버튼 클릭...")
        
        # 정확한 로그인 버튼 셀렉터 (페이지 소스 기준)
        login_button_selectors = [
            "#log\\.login",  # 정확한 셀렉터 (점이 있음)
            "button#log\\.login",  # 더 구체적
            ".btn_login.off.next_step",  # 클래스 기반
            "#frmNIDLogin .btn_login",  # 폼 내 로그인 버튼
            "button:has-text('다음')",  # 텍스트 기반
            "[id='log.login']",  # 속성 기반
        ]
        
        login_clicked = False
        for selector in login_button_selectors:
            try:
                # 버튼이 존재하는지 확인
                button = await page.query_selector(selector)
                if button:
                    # 버튼이 보이고 클릭 가능한지 확인
                    is_visible = await button.is_visible()
                    is_enabled = await button.is_enabled()
                    
                    # 버튼의 텍스트도 확인
                    try:
                        button_text = await button.inner_text()
                        logger.info(f"버튼 셀렉터 {selector}: 존재함, 보임={is_visible}, 활성화={is_enabled}, 텍스트='{button_text}'")
                    except:
                        logger.info(f"버튼 셀렉터 {selector}: 존재함, 보임={is_visible}, 활성화={is_enabled}")
                    
                    if is_visible:  # 활성화 상태와 관계없이 클릭 시도
                        await button.click()
                        logger.info(f"✅ 로그인 버튼 클릭 성공: {selector}")
                        login_clicked = True
                        break
            except Exception as e:
                logger.warning(f"버튼 셀렉터 {selector} 시도 실패: {str(e)}")
                continue
        
        if not login_clicked:
            logger.error("❌ 모든 로그인 버튼 셀렉터 실패")
            # Enter 키로 로그인 시도
            try:
                await page.press("#pw", "Enter")
                logger.info("Enter 키로 로그인 시도")
                login_clicked = True
            except Exception as e:
                logger.error(f"Enter 키 시도도 실패: {str(e)}")
        
        if not login_clicked:
            return LoginResponse(
                success=False,
                message="로그인 버튼을 찾을 수 없습니다"
            )
        
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
            
            # 페이지 제목도 확인
            try:
                page_title = await page.title()
                logger.info(f"페이지 제목: {page_title}")
            except:
                pass
            
            # 오류 메시지 확인 (더 자세히)
            try:
                # 다양한 오류 메시지 셀렉터 확인
                error_selectors = [
                    ".error_msg",
                    ".help_text", 
                    ".alert",
                    ".err",
                    "#err_common",
                    ".login_error",
                    "[class*='error']",
                    "[class*='err']"
                ]
                
                error_found = False
                for selector in error_selectors:
                    elements = await page.query_selector_all(selector)
                    for element in elements:
                        try:
                            error_text = await element.inner_text()
                            if error_text and error_text.strip():
                                logger.warning(f"페이지 오류 메시지 ({selector}): {error_text.strip()}")
                                error_found = True
                        except:
                            pass
                
                if not error_found:
                    logger.info("명시적인 오류 메시지를 찾을 수 없음")
                    
            except Exception as e:
                logger.warning(f"오류 메시지 확인 중 예외: {str(e)}")
            
            # 현재 페이지의 스크린샷 정보 (URL만)
            logger.info(f"현재 페이지 상태 - URL: {current_url}")
            
            # 캡차나 추가 인증이 필요한 경우 체크
            if "captcha" in current_url.lower() or "verify" in current_url.lower():
                return LoginResponse(
                    success=False,
                    message="캡차 또는 추가 인증이 필요합니다"
                )
            elif "nidlogin.login" in current_url:
                # 로그인 페이지에 그대로 있음 - 로그인 실패
                return LoginResponse(
                    success=False,
                    message="로그인에 실패했습니다. 아이디/비밀번호를 확인해주세요"
                )
            elif "nid.naver.com" in current_url:
                # 네이버 인증 관련 페이지
                return LoginResponse(
                    success=False,
                    message="추가 인증이 필요합니다. 수동으로 인증을 완료해주세요"
                )
            else:
                # 다른 페이지로 이동했을 수 있음 (성공적일 수도 있음)
                cookies = await context.cookies()
                cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                
                # 쿠키에 로그인 관련 정보가 있는지 확인
                login_cookies = ['NID_AUT', 'NID_SES', 'NID_JKL']
                has_login_cookies = any(cookie_name in cookie_dict for cookie_name in login_cookies)
                
                if has_login_cookies:
                    return LoginResponse(
                        success=True,
                        message=f"로그인 성공 (현재 URL: {current_url})",
                        cookies=cookie_dict
                    )
                else:
                    return LoginResponse(
                        success=False,
                        message=f"로그인 상태 불확실 (현재 URL: {current_url})"
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
