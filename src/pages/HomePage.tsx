import { Heart, MessageCircle, PawPrint, Plus, ShieldCheck } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { HomeMandatorySearch } from '@/components/home-mandatory-search'
import { MediaImage } from '@/components/media-image'
import '@/home.css'

const homeHeroImage = 'https://images.unsplash.com/photo-1560185008-b033106af5c3?auto=format&fit=crop&w=1920&q=88'

export function HomePage() {
  return (
    <div className="home-page market-home">
      <section className="home-hero" aria-labelledby="home-title">
        <MediaImage src={homeHeroImage} alt="Habitación luminosa con cama, escritorio y ventana" width="1920" height="1080" />
        <div className="home-hero__overlay" />
        <div className="home-hero__content">
          <h1 id="home-title">Solo habitaciones</h1>
          <p>Encuentra una habitación según quién vivirá y sus condiciones.</p>
          <div className="home-hero__chips" aria-label="Condiciones habituales">
            <Badge variant="secondary" className="hero-condition-chip"><PawPrint aria-hidden="true" />Elige tus condiciones</Badge>
          </div>
        </div>
      </section>

      <section className="home-search-stage" aria-label="Configurar búsqueda de habitaciones">
        <Card className="market-search-panel">
          <CardHeader className="sr-only">
            <CardTitle>Configura tu búsqueda</CardTitle>
            <CardDescription>Selecciona al menos una condición antes de acceder a los anuncios.</CardDescription>
          </CardHeader>
          <CardContent className="market-search-panel__content">
            <HomeMandatorySearch />
          </CardContent>
        </Card>
        <div className="home-trust-strip" aria-label="Ventajas de 112233.es">
          <div><ShieldCheck aria-hidden="true" /><span>Anuncios verificados</span></div>
          <Separator orientation="vertical" />
          <div><Heart aria-hidden="true" /><span>Resultados adaptados</span></div>
          <Separator orientation="vertical" />
          <div><MessageCircle aria-hidden="true" /><span>Contacta sin comisión</span></div>
        </div>
      </section>

      <div className="home-publish-action"><Button asChild variant="outline"><Link to="/publicar"><Plus data-icon="inline-start" />Publicar anuncio</Link></Button></div>
    </div>
  )
}
