from pathlib import Path

path = Path('src/pages/PublishPage.tsx')
text = path.read_text(encoding='utf-8')

def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f'Expected exactly one match, found {count}: {old[:120]!r}')
    text = text.replace(old, new, 1)

replace_once(
    '  const content = (() => {\n    switch (step) {',
    '  const renderStep = (targetStep: number) => {\n    switch (targetStep) {',
)
replace_once(
    '\n  })();\n\n  if (published)',
    '\n  };\n\n  if (published)',
)
replace_once(
    '    window.scrollTo({ top: 0, behavior: "smooth" });',
    '    requestAnimationFrame(() => document.getElementById(`publish-section-${value}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));',
)
replace_once(
    '      if (!validate(targetStep)) {\n        setStep(targetStep);\n        return;\n      }',
    '      if (!validate(targetStep)) {\n        setStep(targetStep);\n        requestAnimationFrame(() => document.getElementById(`publish-section-${targetStep}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));\n        return;\n      }',
)
replace_once(
    'return <WizardSection title="Fotografías" description="La primera será la portada. Puedes reordenarlas."><ImageUploader',
    'return <WizardSection title="Fotografías" description="La primera será la portada. Puedes reordenarlas o elegir otra portada sin borrar ni volver a subir fotos."><ImageUploader',
)
replace_once(
    '<div className="container wizard-layout"><aside><Stepper steps={steps} current={step} maxVisited={maxVisited} onStep={(value) => { if (recoveringImages && value !== 6 && value !== steps.length - 1) return; setStep(value); }} /></aside><section className="wizard-content" aria-label="Formulario del anuncio">',
    '<div className="container wizard-layout publish-single-page"><aside><Stepper steps={steps} current={step} maxVisited={maxVisited} onStep={(value) => { if (recoveringImages && value !== 6 && value !== steps.length - 1) return; setStep(value); requestAnimationFrame(() => document.getElementById(`publish-section-${value}`)?.scrollIntoView({ behavior: "smooth", block: "start" })); }} /></aside><section className="wizard-content" aria-label="Formulario del anuncio">',
)
replace_once(
    '<Button type="button" variant="outline" onClick={() => setStep(6)}>Revisar fotografías</Button>',
    '<Button type="button" variant="outline" onClick={() => { setStep(6); requestAnimationFrame(() => document.getElementById("publish-section-6")?.scrollIntoView({ behavior: "smooth", block: "start" })); }}>Revisar fotografías</Button>',
)
replace_once(
    '        <fieldset className="publish-recovery-fields" disabled={recoveringImages && step !== 6}>{content}</fieldset>',
    '        <div className="publish-single-page__sections">{steps.map((label, index) => <div className="publish-single-page__section" id={`publish-section-${index}`} data-publish-step={index} key={label}><fieldset className="publish-recovery-fields" disabled={recoveringImages && index !== 6}>{renderStep(index)}</fieldset></div>)}</div>',
)
marker = '  if (editing && (!existing || !canManageListing(existing))) return <Navigate to="/mis-anuncios" replace />;'
insert = '''  useEffect(() => {\n    const sections = Array.from(document.querySelectorAll<HTMLElement>("[data-publish-step]"));\n    if (!sections.length || typeof IntersectionObserver === "undefined") return;\n    const observer = new IntersectionObserver((entries) => {\n      const visible = entries.filter((entry) => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];\n      if (!visible) return;\n      const value = Number((visible.target as HTMLElement).dataset.publishStep);\n      if (!Number.isInteger(value)) return;\n      setStep(value);\n      setMaxVisited((current) => Math.max(current, value));\n    }, { rootMargin: "-18% 0px -65% 0px", threshold: [0, 0.05, 0.2, 0.5] });\n    sections.forEach((section) => observer.observe(section));\n    return () => observer.disconnect();\n  }, [published, recoveringImages]);\n'''
replace_once(marker, insert + marker)

path.write_text(text, encoding='utf-8')
print('Updated', path)
