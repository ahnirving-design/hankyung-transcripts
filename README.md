# hankyung-transcripts

한경코리아마켓 「모닝루틴(한국경제신문 30분 만에 읽기)」 평일 라이브의 유튜브 자막을 매일 수집한다.

- 수집: GitHub Actions(`.github/workflows/fetch-transcript.yml`)가 평일 KST 10:30·11:30·13:00에 실행. 이미 저장된 날은 건너뜀.
- 결과: `transcripts/hankyung_YYYY-MM-DD_transcript.md`
- 수동 실행: Actions 탭 → "모닝루틴 자막 수집" → Run workflow (날짜 입력 가능)
- 리포트: Claude 예약 작업이 이 파일을 읽어 「한경 30분 요약」 리포트를 작성.

자막은 유튜브 자동 생성 자막이라 고유명사·숫자·단위 오인식이 있을 수 있다.
