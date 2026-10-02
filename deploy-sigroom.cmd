@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion
cd /d "%~dp0"
title SIGROOM - deploy ขึ้นเว็บจริง

echo ============================================================
echo   SIGROOM - ปุ่มเดียว deploy ขึ้นเว็บจริง (production)
echo ============================================================
echo.
echo สิ่งที่โปรแกรมนี้จะทำ (ตามลำดับ):
echo   1. ตรวจความพร้อม (ยังไม่แก้อะไรบนเว็บจริง)
echo   2. สร้างและอัปเดตระบบบน Cloud Run พร้อมปรับฐานข้อมูล (migrate)
echo   3. อัปโหลดหน้าเปิดระบบและไฟล์ static ขึ้น Firebase Hosting
echo   4. ตรวจว่าเว็บเปิดได้จริง
echo.

for /f "delims=" %%i in ('git rev-parse HEAD 2^>nul') do set "SHA=%%i"
if not defined SHA (
  echo [ไม่สำเร็จ] อ่านเวอร์ชันโค้ดจาก git ไม่ได้ - ตรวจว่าเปิดไฟล์นี้จากโฟลเดอร์โปรเจกต์ และติดตั้ง git แล้ว
  goto :end
)

echo กำลังตรวจความพร้อม...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy-sigroom-production.ps1" -CommitSha !SHA!
if errorlevel 1 (
  echo.
  echo [ไม่สำเร็จ] ตรวจความพร้อมไม่ผ่าน - ยังไม่มีอะไรถูก deploy
  echo ถ้าข้อความด้านบนบอกว่า worktree is not clean แปลว่ามีไฟล์ที่ยังไม่ได้ commit ให้ commit ให้เรียบร้อยก่อน
  goto :end
)

echo.
echo ------------------------------------------------------------
echo   ผ่านการตรวจความพร้อมแล้ว พร้อม deploy เวอร์ชันนี้ขึ้นเว็บจริง
echo   รหัสเวอร์ชัน : !SHA!
echo   ข้อความล่าสุด:
git log -1 --format="    %%s"
echo ------------------------------------------------------------
echo.
echo การ deploy จะกระทบผู้ใช้เว็บจริงทันที
set "ANSWER="
set /p "ANSWER=ถ้าต้องการ deploy ให้พิมพ์คำว่า DEPLOY (ตัวพิมพ์ใหญ่) แล้วกด Enter - พิมพ์อย่างอื่นหรือกด Enter เฉย ๆ เพื่อยกเลิก: "
if not "!ANSWER!"=="DEPLOY" (
  echo.
  echo ยกเลิกแล้ว - ไม่มีอะไรถูก deploy
  goto :end
)

echo.
echo เริ่ม deploy... (ใช้เวลาหลายนาที อย่าปิดหน้าต่างนี้)
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\deploy-sigroom-production.ps1" -CommitSha !SHA! -Deploy -ConfirmProduction DEPLOY
if errorlevel 1 (
  echo.
  echo ============================================================
  echo   [ไม่สำเร็จ] deploy มีปัญหา - อ่านข้อความสีแดงด้านบน แล้วแจ้งผู้ดูแลระบบ
  echo   หมายเหตุ: ถ้า Cloud Build ผ่านแต่ Firebase ไม่ผ่าน ให้รันไฟล์นี้ซ้ำได้ ไม่เสียหาย
  echo ============================================================
  goto :end
)

echo.
echo ============================================================
echo   [สำเร็จ] deploy เรียบร้อย - เว็บจริงเป็นเวอร์ชันล่าสุดแล้ว
echo ============================================================

:end
echo.
pause
endlocal
