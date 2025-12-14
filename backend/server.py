from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List
import uuid
from datetime import datetime, timezone
import re
import asyncio
from playwright.async_api import async_playwright
from openpyxl import Workbook
from openpyxl.drawing.image import Image as XLImage
from PIL import Image
import io
import tempfile

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Set Playwright browser path
os.environ['PLAYWRIGHT_BROWSERS_PATH'] = '/pw-browsers'

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class SpeedTestRequest(BaseModel):
    urls: List[str]

class SpeedTestResponse(BaseModel):
    success: bool
    message: str
    file_path: str = None
    errors: List[str] = []

# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


def validate_speedtest_url(url: str) -> bool:
    """Validate if URL is a valid speedtest.net result link"""
    pattern = r'^https://www\.speedtest\.net/my-result/(a|d|i)/\d+$'
    return bool(re.match(pattern, url.strip()))


async def capture_speedtest_screenshot(url: str) -> bytes:
    """Capture screenshot of speedtest result page"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox']
        )
        
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            # Navigate with longer timeout and different wait strategy
            await page.goto(url, wait_until='domcontentloaded', timeout=60000)
            
            # Wait for page to be ready - try multiple selectors
            try:
                await page.wait_for_selector('.result-container-speed-test', timeout=15000)
            except:
                try:
                    await page.wait_for_selector('.result-data', timeout=10000)
                except:
                    # If specific selectors fail, just wait a bit for general content
                    await page.wait_for_timeout(5000)
            
            # Additional wait for any dynamic content
            await page.wait_for_timeout(2000)
            
            # Take screenshot
            screenshot_bytes = await page.screenshot(full_page=True, type='png')
            return screenshot_bytes
        finally:
            await context.close()
            await browser.close()


def create_excel_with_screenshots(screenshot_data: List[tuple]) -> str:
    """Create Excel file with screenshots. 5 images per row, skip column, then next image.
    
    Args:
        screenshot_data: List of tuples (url, screenshot_bytes)
    
    Returns:
        Path to created Excel file
    """
    wb = Workbook()
    ws = wb.active
    ws.title = "Speedtest Results"
    
    # Set column widths and row heights
    for col in range(1, 50):  # Prepare enough columns
        ws.column_dimensions[chr(64 + col) if col <= 26 else f"A{chr(64 + col - 26)}"].width = 20
    
    current_row = 1
    current_col = 1
    images_in_row = 0
    
    for idx, (url, screenshot_bytes) in enumerate(screenshot_data):
        # Process image
        img = Image.open(io.BytesIO(screenshot_bytes))
        
        # Resize image to fit in cell (approx 400px width)
        aspect_ratio = img.height / img.width
        new_width = 400
        new_height = int(new_width * aspect_ratio)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to temporary buffer
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        # Create Excel image
        xl_img = XLImage(img_buffer)
        
        # Calculate cell position
        # 5 images per row, then skip a column
        if images_in_row >= 5:
            current_row += 30  # Move to next row (leave space for image height)
            current_col = 1
            images_in_row = 0
        
        # Get column letter
        col_letter = chr(64 + current_col) if current_col <= 26 else f"A{chr(64 + current_col - 26)}"
        cell_position = f"{col_letter}{current_row}"
        
        # Add URL as text in the cell
        ws[cell_position] = url
        
        # Add image
        xl_img.anchor = cell_position
        ws.add_image(xl_img)
        
        # Move to next position (skip a column after each image)
        current_col += 2
        images_in_row += 1
    
    # Save file
    temp_dir = Path("/tmp/speedtest_results")
    temp_dir.mkdir(exist_ok=True)
    
    file_path = temp_dir / f"speedtest_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb.save(str(file_path))
    
    return str(file_path)


@api_router.post("/process-speedtest")
async def process_speedtest(request: SpeedTestRequest):
    """Process speedtest URLs and generate Excel with screenshots"""
    if not request.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    
    # Validate URLs
    invalid_urls = []
    valid_urls = []
    
    for url in request.urls:
        url = url.strip()
        if not url:
            continue
        if validate_speedtest_url(url):
            valid_urls.append(url)
        else:
            invalid_urls.append(url)
    
    if not valid_urls:
        raise HTTPException(
            status_code=400,
            detail="No valid speedtest.net URLs found"
        )
    
    # Capture screenshots
    screenshot_data = []
    errors = []
    
    for url in valid_urls:
        try:
            logger.info(f"Capturing screenshot for: {url}")
            screenshot_bytes = await capture_speedtest_screenshot(url)
            screenshot_data.append((url, screenshot_bytes))
        except Exception as e:
            logger.error(f"Error capturing {url}: {str(e)}")
            errors.append(f"Failed to capture {url}: {str(e)}")
    
    if not screenshot_data:
        raise HTTPException(
            status_code=500,
            detail="Failed to capture any screenshots"
        )
    
    # Create Excel file
    try:
        file_path = create_excel_with_screenshots(screenshot_data)
        return {
            "success": True,
            "message": f"Successfully processed {len(screenshot_data)} URLs",
            "file_path": file_path,
            "errors": errors + [f"Invalid URL: {url}" for url in invalid_urls]
        }
    except Exception as e:
        logger.error(f"Error creating Excel: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error creating Excel file: {str(e)}"
        )


@api_router.get("/download/{file_name}")
async def download_file(file_name: str):
    """Download generated Excel file"""
    file_path = Path("/tmp/speedtest_results") / file_name
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=file_name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
