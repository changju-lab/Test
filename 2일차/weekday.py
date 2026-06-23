import sys
from calendar import monthcalendar

# 요일 헤더 (월요일부터 시작)
WEEKDAY_HEADERS = ("월", "화", "수", "목", "금", "토", "일")

# 터미널 색상 코드 (ANSI escape sequence)
BLUE = "\033[34m"   # 토요일
RED = "\033[31m"    # 일요일
RESET = "\033[0m"   # 색상 초기화


def enable_ansi_colors() -> None:
    """Windows 터미널에서 ANSI 색상 출력을 활성화한다."""
    if sys.platform == "win32":
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # stdout 핸들
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING 플래그 추가
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)


def colorize(text: str, weekday_index: int) -> str:
    """요일 인덱스에 따라 텍스트에 색상을 적용한다. (5=토, 6=일)"""
    if weekday_index == 5:
        return f"{BLUE}{text}{RESET}"
    if weekday_index == 6:
        return f"{RED}{text}{RESET}"
    return text


def print_calendar(year: int, month: int) -> None:
    """입력받은 년·월의 달력을 요일 헤더와 함께 출력한다."""
    # monthcalendar: 해당 월을 주 단위 리스트로 반환 (0은 빈 칸)
    weeks = monthcalendar(year, month)

    print(f"\n{year}년 {month}월")
    # 요일 헤더 출력 (토·일은 색상 적용)
    print(
        " ".join(
            colorize(f"{day:>3}", index)
            for index, day in enumerate(WEEKDAY_HEADERS)
        )
    )
    print("-" * 22)

    # 각 주(행)를 순회하며 날짜 출력
    for week in weeks:
        row = []
        for weekday_index, day in enumerate(week):
            if day == 0:
                row.append("   ")  # 이전/다음 달 날짜 자리
            else:
                row.append(colorize(f"{day:3d}", weekday_index))
        print(" ".join(row))


def main() -> None:
    enable_ansi_colors()
    print("년, 월을 입력하면 해당 달의 달력을 보여드립니다.")
    year = int(input("년: "))
    month = int(input("월: "))
    day = int(input("일: "))
    print_calendar(year, month)


if __name__ == "__main__":
    main()
