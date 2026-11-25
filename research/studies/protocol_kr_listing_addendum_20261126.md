# Addendum 2026-11-26 to protocol_kr_listing_20261126.md: the one allowed parser fix (before the freeze, no price read)

Stage A (run 45670448929) read titles only. Reading the unmatched titles showed that Upbit/Bithumb edit a notice after posting by appending a note such as
"(거래지원 개시 시점 연기 안내)", "(Delay in start of Market Support)", "(입금 오픈 시간 변경)"; when the earliest capture already carries the note, the locked title
filter dropped real listings (e.g. ZRO, CKB, MOVE, B3, IRYS, CC, VIRTUAL) because of the words 변경/연기. Notice time is unaffected (`first_listed_at` / page date are the original post time).
Fix (core/kr_listing.py `strip_notes`): trailing parenthetical notes with schedule/withdrawal words are stripped before the exclusion test (a note with 취소/종료/폐지/cancel/terminat keeps the exclusion);
`에어드랍/에어드롭` is no longer an exclusion word on its own (a listing may carry a foundation airdrop in the same title), `이벤트 / 지급 / 상장 기념` still exclude.
Nothing else changes: rules, delays, holds, costs, stops, control, gate, splits are as locked. This is the single parser fix; the events are then re-frozen and priced once.
