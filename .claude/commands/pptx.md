# /pptx — 대성쎌틱에너시스 PPT 생성기

PowerPoint(PPTX) 파일을 Node.js + pptxgenjs 라이브러리를 사용해 자동 생성하는 명령어입니다.

## 사용법

```
/pptx <요청 내용>
```

**예시:**
- `/pptx 대성 블랙 콘덴싱 제품 소개 보고서 만들어줘`
- `/pptx 2026년 2분기 마케팅 캠페인 기획안 PPT`
- `/pptx 환절기 난방 관리 콘텐츠 제안서`

---

## 실행 지침

이 명령어가 호출되면 다음 순서로 실행합니다:

### 1단계 — 슬라이드 구성 기획

요청 내용을 분석해 슬라이드 구성을 먼저 설계합니다:
- 발표 목적과 타겟 청중 파악
- 슬라이드 수 결정 (일반적으로 8~15장)
- 각 슬라이드 제목과 핵심 내용 구성
- `_context/brand-guideline.md` 참조해 브랜드 톤 적용
- `_templates/ppt design/` 참조해 디자인 방향 확인

### 2단계 — Node.js 스크립트 생성 및 실행

아래 템플릿을 기반으로 Node.js 스크립트를 작성하고 Bash로 실행합니다:

```javascript
// pptx-gen.js (임시 실행 후 삭제)
const PptxGenJS = require('pptxgenjs');
const pptx = new PptxGenJS();

// 브랜드 컬러 상수
const BRAND = {
  red:       'C8102E',
  black:     '1A1A1A',
  white:     'FFFFFF',
  darkGray:  '333333',
  midGray:   '666666',
  lightGray: 'F5F5F3',
};

// 슬라이드 레이아웃 설정
pptx.layout = 'LAYOUT_WIDE'; // 16:9

// ── 표지 슬라이드 ──────────────────────────────────
const cover = pptx.addSlide();
cover.background = { color: BRAND.black };
cover.addText('{{제목}}', {
  x: 0.8, y: 2.5, w: 11, h: 1.2,
  fontSize: 36, bold: true, color: BRAND.white,
  fontFace: 'Malgun Gothic',
});
cover.addText('대성쎌틱에너시스', {
  x: 0.8, y: 3.9, w: 6, h: 0.5,
  fontSize: 14, color: BRAND.red,
  fontFace: 'Malgun Gothic',
});
cover.addText('{{날짜}}', {
  x: 0.8, y: 4.5, w: 6, h: 0.4,
  fontSize: 12, color: 'AAAAAA',
  fontFace: 'Malgun Gothic',
});

// ── 목차 슬라이드 ──────────────────────────────────
const toc = pptx.addSlide();
toc.background = { color: BRAND.white };
toc.addText('목차', {
  x: 0.8, y: 0.5, w: 11, h: 0.8,
  fontSize: 28, bold: true, color: BRAND.black,
  fontFace: 'Malgun Gothic',
});
// 좌측 레드 바
toc.addShape(pptx.ShapeType.rect, {
  x: 0.8, y: 1.4, w: 0.08, h: 4,
  fill: { color: BRAND.red },
  line: { color: BRAND.red },
});
// 목차 항목들
const tocItems = [
  '01. {{섹션1}}',
  '02. {{섹션2}}',
  '03. {{섹션3}}',
  '04. {{섹션4}}',
];
tocItems.forEach((item, i) => {
  toc.addText(item, {
    x: 1.1, y: 1.5 + i * 0.9, w: 10, h: 0.7,
    fontSize: 16, color: BRAND.darkGray,
    fontFace: 'Malgun Gothic',
  });
});

// ── 본문 슬라이드 (반복 패턴) ──────────────────────
function addContentSlide(pptx, title, bullets) {
  const slide = pptx.addSlide();
  slide.background = { color: BRAND.white };
  
  // 상단 레드 헤더 바
  slide.addShape(pptx.ShapeType.rect, {
    x: 0, y: 0, w: 13.33, h: 1.1,
    fill: { color: BRAND.black },
    line: { color: BRAND.black },
  });
  slide.addText(title, {
    x: 0.5, y: 0.15, w: 12, h: 0.8,
    fontSize: 22, bold: true, color: BRAND.white,
    fontFace: 'Malgun Gothic',
  });
  
  // 본문 불릿 포인트
  bullets.forEach((bullet, i) => {
    slide.addShape(pptx.ShapeType.rect, {
      x: 0.8, y: 1.5 + i * 0.85, w: 0.12, h: 0.12,
      fill: { color: BRAND.red },
      line: { color: BRAND.red },
    });
    slide.addText(bullet, {
      x: 1.1, y: 1.4 + i * 0.85, w: 11, h: 0.7,
      fontSize: 14, color: BRAND.darkGray,
      fontFace: 'Malgun Gothic',
      breakLine: false,
    });
  });
  
  // 하단 푸터
  slide.addText('대성쎌틱에너시스 | Confidential', {
    x: 0.5, y: 6.8, w: 12, h: 0.3,
    fontSize: 9, color: BRAND.midGray,
    fontFace: 'Malgun Gothic', align: 'right',
  });
  return slide;
}

// 본문 슬라이드 추가 예시
addContentSlide(pptx, '{{섹션 제목}}', [
  '{{핵심 내용 1}}',
  '{{핵심 내용 2}}',
  '{{핵심 내용 3}}',
]);

// ── 마지막 슬라이드 ─────────────────────────────────
const end = pptx.addSlide();
end.background = { color: BRAND.black };
end.addText('마음보일러 ON!', {
  x: 0, y: 2.2, w: 13.33, h: 1,
  fontSize: 32, bold: true, color: BRAND.red,
  fontFace: 'Malgun Gothic', align: 'center',
});
end.addText('대성쎌틱에너시스', {
  x: 0, y: 3.4, w: 13.33, h: 0.6,
  fontSize: 16, color: BRAND.white,
  fontFace: 'Malgun Gothic', align: 'center',
});
end.addText('www.celtic.co.kr', {
  x: 0, y: 4.1, w: 13.33, h: 0.5,
  fontSize: 13, color: 'AAAAAA',
  fontFace: 'Malgun Gothic', align: 'center',
});

// 파일 저장
await pptx.writeFile({ fileName: '{{출력파일명}}.pptx' });
console.log('✓ PPTX 생성 완료: {{출력파일명}}.pptx');
```

### 3단계 — 스크립트 실행

```bash
node /tmp/pptx-gen.js
```

### 4단계 — 결과 보고

- 생성된 파일 경로 안내
- 슬라이드 구성 요약 제공
- 수정 요청 시 스크립트 수정 후 재실행

---

## 브랜드 적용 원칙

- **컬러**: 레드 `#C8102E`, 블랙 `#1A1A1A`, 화이트 `#FFFFFF`
- **폰트**: Malgun Gothic (한국어 기본)
- **레이아웃**: LAYOUT_WIDE (16:9 와이드스크린)
- **표지**: 블랙 배경 + 화이트 제목 + 레드 브랜드명
- **본문**: 화이트 배경 + 블랙 헤더 바 + 레드 불릿
- **마지막**: 블랙 배경 + "마음보일러 ON!" + 웹사이트

## 저장 위치

별도 지정이 없으면 현재 작업 디렉토리(프로젝트 루트)에 저장합니다.
