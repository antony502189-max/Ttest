import { HomeAISearch } from '@/components/home-ai-search'

export function HomePage() {
  return <main style={{ maxWidth: 1100, margin: '40px auto', padding: '0 20px' }} data-i18n-exempt>
    <p style={{ color: '#46672d' }}>112233.es · доступ владельцу и команде</p>
    <h1 style={{ fontSize: 'clamp(28px, 5vw, 48px)', fontWeight: 700, margin: '12px 0' }}>Поиск жилья с AI</h1>
    <p style={{ marginBottom: 16 }}>Опишите бюджет, посмотрите реальные объявления и уточните условия в том же диалоге.</p>
    <div style={{ padding: 20, border: '1px solid #d5e5bc', borderRadius: 16, background: '#f6faee', marginBottom: 24 }}>
      <strong>Первый тест: цена за месяц</strong>
      <p>Введите «до 600 евро в месяц», затем «теперь до 400 евро в месяц». Для снятия бюджета: «убери ограничение бюджета».</p>
      <p>Также можно: “rooms under 500 euros per month” или “habitaciones hasta 500 euros al mes”.</p>
      <p>Диапазон €50–1000. Другие условия пока не поддерживаются. Не вводите имена, контакты или личные сведения.</p>
    </div>
    <HomeAISearch homeMode="long" initialRentalMode="long" />
    <p style={{ margin: '24px 0', color: '#596454', fontSize: 14 }}>Данные: ограниченный снимок публичных объявлений PisoCompartido, а не весь каталог Испании. Карта показывает координатную сетку. Фото из внешних источников в пилоте закрыты. Голос, сохранение и уведомления ещё не включены.</p>
  </main>
}
