from pathlib import Path

path = Path('src/pages/PublishPage.tsx')
text = path.read_text(encoding='utf-8')
old = '<Button variant="outline" disabled={step === 0 || publishing || recoveringImages} onClick={() => setStep((value) => value - 1)}><ArrowLeft data-icon="inline-start" />Atrás</Button>'
new = '<Button variant="outline" disabled={step === 0 || publishing || recoveringImages} onClick={() => { const value = Math.max(0, step - 1); setStep(value); requestAnimationFrame(() => document.getElementById(`publish-section-${value}`)?.scrollIntoView({ behavior: "smooth", block: "start" })); }}><ArrowLeft data-icon="inline-start" />Atrás</Button>'
if text.count(old) != 1:
    raise SystemExit(f'Expected one Back button match, found {text.count(old)}')
path.write_text(text.replace(old, new, 1), encoding='utf-8')
print('Updated Back navigation')
