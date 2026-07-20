import { useState, type ReactNode } from "react";
import {
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  Eye,
  FileCheck2,
  Info,
  MapPin,
  Save,
} from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Checkbox } from "@/components/ui/checkbox";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { FormField, ImageUploader, Stepper } from "@/components/forms";
import {
  PropertyCard,
  PropertyGallery,
  PropertyBadge,
} from "@/components/marketplace";
import { listings } from "@/data/listings";

const steps = [
  "Tipo de alquiler",
  "Ubicación",
  "Datos de la habitación",
  "Precio y gastos",
  "Disponibilidad",
  "Convivencia",
  "Fotografías",
  "Descripción",
  "Contacto",
  "Vista previa",
];

function ChoiceCards({
  name,
  options,
  defaultValue,
}: {
  name: string;
  options: { title: string; text: string }[];
  defaultValue?: number;
}) {
  return (
    <div className="wizard-choice-grid">
      {options.map((option, index) => (
        <label key={option.title}>
          <input
            type="radio"
            name={name}
            defaultChecked={index === (defaultValue ?? 0)}
          />
          <span>
            <strong>{option.title}</strong>
            <small>{option.text}</small>
          </span>
        </label>
      ))}
    </div>
  );
}

function WizardSection({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="wizard-section">
      <header>
        <h2>{title}</h2>
        <p>{description}</p>
      </header>
      {children}
    </section>
  );
}

function StepContent({ step }: { step: number }) {
  const preview = listings[0];
  switch (step) {
    case 0:
      return (
        <WizardSection
          title="¿Qué tipo de estancia ofreces?"
          description="Esto cambia cómo mostramos el precio, las fechas y la duración."
        >
          <ChoiceCards
            name="rental-mode"
            options={[
              {
                title: "Larga estancia",
                text: "Alquiler mensual para vivir durante varios meses.",
              },
              {
                title: "Alquiler vacacional",
                text: "Estancias cortas con precio por noche.",
              },
            ]}
          />
          <Alert>
            <Info />
            <AlertTitle>Información clara desde el principio</AlertTitle>
            <AlertDescription>
              Podrás indicar una estancia mínima y fechas concretas más
              adelante.
            </AlertDescription>
          </Alert>
        </WizardSection>
      );
    case 1:
      return (
        <WizardSection
          title="Sitúa la habitación"
          description="Publicaremos una zona aproximada. La dirección exacta nunca aparece en el mapa público."
        >
          <div className="form-grid">
            <FormField label="Municipio" htmlFor="publish-city">
              <select id="publish-city" defaultValue="Adeje">
                <option>Adeje</option>
                <option>Arona</option>
                <option>Granadilla de Abona</option>
                <option>Santa Cruz de Tenerife</option>
                <option>San Cristóbal de La Laguna</option>
              </select>
            </FormField>
            <FormField label="Zona o barrio" htmlFor="publish-area">
              <Input id="publish-area" defaultValue="Armeñime" />
            </FormField>
            <FormField label="Calle" htmlFor="publish-street">
              <Input
                id="publish-street"
                placeholder="Solo para verificación interna"
              />
            </FormField>
            <FormField label="Código postal" htmlFor="publish-postcode">
              <Input
                id="publish-postcode"
                inputMode="numeric"
                defaultValue="38678"
              />
            </FormField>
          </div>
          <div className="location-preview">
            <MapPin />
            <div>
              <strong>Armeñime, Adeje</strong>
              <span>Mostraremos un punto aproximado en un radio de 300 m.</span>
            </div>
          </div>
        </WizardSection>
      );
    case 2:
      return (
        <WizardSection
          title="Describe la habitación y la vivienda"
          description="Estos datos ayudan a comparar sin tener que preguntar lo básico."
        >
          <ChoiceCards
            name="room-type"
            options={[
              { title: "Individual", text: "Para una persona." },
              { title: "Compartida", text: "Dos o más camas." },
              { title: "Estudio", text: "Espacio autónomo." },
            ]}
          />
          <div className="form-grid">
            <FormField label="Tamaño aproximado" htmlFor="publish-size">
              <Input id="publish-size" type="number" defaultValue="12" />
              <span className="input-suffix">m²</span>
            </FormField>
            <FormField
              label="Personas que viven en casa"
              htmlFor="publish-people"
            >
              <Input
                id="publish-people"
                type="number"
                defaultValue="4"
                min="0"
              />
            </FormField>
            <FormField label="Baño" htmlFor="publish-bath">
              <select id="publish-bath">
                <option>Compartido</option>
                <option>Privado</option>
              </select>
            </FormField>
            <FormField label="Cocina" htmlFor="publish-kitchen">
              <select id="publish-kitchen">
                <option>Compartida</option>
                <option>Privada</option>
              </select>
            </FormField>
          </div>
          <fieldset className="checks-panel">
            <legend>Equipamiento</legend>
            {[
              "Amueblada",
              "Escritorio",
              "Armario",
              "Ventana exterior",
              "Cerradura privada",
              "Aire acondicionado",
            ].map((item) => (
              <label key={item}>
                <Checkbox
                  defaultChecked={[
                    "Amueblada",
                    "Escritorio",
                    "Armario",
                  ].includes(item)}
                />
                {item}
              </label>
            ))}
          </fieldset>
        </WizardSection>
      );
    case 3:
      return (
        <WizardSection
          title="Precio, gastos y fianza"
          description="Separa cada concepto. Los anuncios transparentes reciben contactos más útiles."
        >
          <div className="form-grid">
            <FormField label="Alquiler mensual" htmlFor="publish-price">
              <Input id="publish-price" type="number" defaultValue="450" />
              <span className="input-suffix">€ / mes</span>
            </FormField>
            <FormField label="Fianza" htmlFor="publish-deposit">
              <Input id="publish-deposit" type="number" defaultValue="450" />
              <span className="input-suffix">€</span>
            </FormField>
          </div>
          <fieldset className="checks-panel">
            <legend>Gastos incluidos</legend>
            {[
              "Agua",
              "Electricidad",
              "Internet",
              "Limpieza de zonas comunes",
            ].map((item) => (
              <label key={item}>
                <Checkbox defaultChecked />
                {item}
              </label>
            ))}
          </fieldset>
          <FormField
            label="Límite o aclaración sobre gastos"
            htmlFor="publish-bills-note"
          >
            <Input
              id="publish-bills-note"
              defaultValue="Todo incluido con uso responsable"
            />
          </FormField>
        </WizardSection>
      );
    case 4:
      return (
        <WizardSection
          title="Disponibilidad"
          description="Indica cuándo puede entrar la próxima persona y cuánto tiempo debe quedarse."
        >
          <div className="form-grid">
            <FormField label="Disponible desde" htmlFor="publish-available">
              <Input
                id="publish-available"
                type="date"
                defaultValue="2026-08-01"
              />
            </FormField>
            <FormField label="Estancia mínima" htmlFor="publish-min-stay">
              <select id="publish-min-stay" defaultValue="3 meses">
                <option>1 mes</option>
                <option>2 meses</option>
                <option>3 meses</option>
                <option>6 meses</option>
                <option>Curso académico</option>
              </select>
            </FormField>
            <FormField
              label="Fecha límite del anuncio"
              htmlFor="publish-expiry"
            >
              <Input
                id="publish-expiry"
                type="date"
                defaultValue="2026-10-01"
              />
            </FormField>
          </div>
        </WizardSection>
      );
    case 5:
      return (
        <WizardSection
          title="Condiciones de convivencia"
          description="Exprésalas de forma neutral, concreta y visible. Evita criterios que puedan resultar ilegales o discriminatorios."
        >
          <fieldset className="checks-panel checks-panel--columns">
            <legend>Convivencia</legend>
            {[
              "Una persona",
              "Parejas permitidas",
              "Niños permitidos",
              "Mascotas permitidas",
              "Se puede fumar",
              "Empadronamiento posible",
              "Visitas ocasionales",
              "Teletrabajo permitido",
            ].map((item) => (
              <label key={item}>
                <Checkbox
                  defaultChecked={[
                    "Una persona",
                    "Teletrabajo permitido",
                  ].includes(item)}
                />
                {item}
              </label>
            ))}
          </fieldset>
          <FormField
            label="Normas de la vivienda"
            htmlFor="publish-rules"
            description="No incluyas datos personales ni criterios discriminatorios."
          >
            <Textarea
              id="publish-rules"
              rows={5}
              defaultValue="Buscamos una convivencia tranquila. Se respetan los horarios de descanso y se organizan turnos de limpieza semanales."
            />
          </FormField>
        </WizardSection>
      );
    case 6:
      return (
        <WizardSection
          title="Fotografías"
          description="Empieza por la habitación. Añade después baño, cocina y zonas comunes."
        >
          <ImageUploader />
        </WizardSection>
      );
    case 7:
      return (
        <WizardSection
          title="Cuenta cómo es vivir aquí"
          description="Un buen título es específico; una buena descripción responde las dudas habituales."
        >
          <FormField
            label="Título del anuncio"
            htmlFor="publish-title"
            description="Máximo 80 caracteres."
          >
            <Input
              id="publish-title"
              maxLength={80}
              defaultValue="Habitación luminosa con escritorio y gastos incluidos"
            />
          </FormField>
          <FormField
            label="Descripción"
            htmlFor="publish-description"
            description="Incluye ambiente, conexiones y cómo es la convivencia."
          >
            <Textarea
              id="publish-description"
              rows={8}
              defaultValue={preview.description}
            />
          </FormField>
        </WizardSection>
      );
    case 8:
      return (
        <WizardSection
          title="Datos de contacto"
          description="Elige cómo pueden hablar contigo las personas interesadas."
        >
          <div className="form-grid">
            <FormField label="Nombre público" htmlFor="publish-contact-name">
              <Input
                id="publish-contact-name"
                defaultValue="Equipo Casa Norte"
              />
            </FormField>
            <FormField label="Teléfono" htmlFor="publish-contact-phone">
              <Input
                id="publish-contact-phone"
                type="tel"
                defaultValue="+34 600 112 233"
              />
            </FormField>
            <FormField label="WhatsApp" htmlFor="publish-contact-whatsapp">
              <Input
                id="publish-contact-whatsapp"
                type="tel"
                defaultValue="+34 600 112 233"
              />
            </FormField>
            <FormField label="Telegram" htmlFor="publish-contact-telegram">
              <Input
                id="publish-contact-telegram"
                defaultValue="@casa_norte_demo"
              />
            </FormField>
            <FormField label="Email" htmlFor="publish-contact-email">
              <Input
                id="publish-contact-email"
                type="email"
                defaultValue="anuncios@example.es"
              />
            </FormField>
          </div>
          <fieldset className="checks-panel">
            <legend>Canales disponibles</legend>
            <label>
              <Checkbox defaultChecked />
              WhatsApp
            </label>
            <label>
              <Checkbox defaultChecked />
              Telegram
            </label>
            <label>
              <Checkbox defaultChecked />
              Teléfono
            </label>
          </fieldset>
        </WizardSection>
      );
    default:
      return (
        <WizardSection
          title="Revisa antes de publicar"
          description="Así verá tu anuncio una persona que esté comparando habitaciones."
        >
          <Alert>
            <FileCheck2 />
            <AlertTitle>El anuncio está completo</AlertTitle>
            <AlertDescription>
              Revisa sobre todo el precio, las condiciones y la fecha de
              entrada.
            </AlertDescription>
          </Alert>
          <div className="preview-card-wrap">
            <PropertyCard listing={preview} />
          </div>
          <div className="preview-conditions">
            <h3>Condiciones visibles</h3>
            <div className="badge-row">
              {preview.restrictions.map((item) => (
                <PropertyBadge key={item}>{item}</PropertyBadge>
              ))}
            </div>
          </div>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="outline">
                <Eye data-icon="inline-start" />
                Vista previa completa
              </Button>
            </DialogTrigger>
            <DialogContent className="full-preview-dialog">
              <DialogHeader>
                <DialogTitle>Vista previa del anuncio</DialogTitle>
                <DialogDescription>
                  Versión de escritorio de tu página pública.
                </DialogDescription>
              </DialogHeader>
              <PropertyGallery listing={preview} />
              <h2>{preview.title}</h2>
              <p>{preview.description}</p>
            </DialogContent>
          </Dialog>
        </WizardSection>
      );
  }
}

export function PublishPage({ editing = false }: { editing?: boolean }) {
  const { id } = useParams();
  const [step, setStep] = useState(0);
  const [published, setPublished] = useState(false);
  if (published)
    return (
      <div className="publish-success">
        <CheckCircle2 />
        <span className="eyebrow">Anuncio enviado</span>
        <h1>
          {editing ? "Cambios guardados" : "Tu habitación está en revisión"}
        </h1>
        <p>
          Te avisaremos cuando pase la revisión. Mientras tanto puedes seguir
          editando el borrador.
        </p>
        <div>
          <Button asChild>
            <Link to="/mis-anuncios">Ver mis anuncios</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/buscar">Ir a buscar</Link>
          </Button>
        </div>
      </div>
    );
  return (
    <div className="publish-page">
      <div className="container publish-header">
        <Button asChild variant="ghost">
          <Link to="/mis-anuncios">
            <ArrowLeft data-icon="inline-start" />
            Salir
          </Link>
        </Button>
        <div>
          <span className="eyebrow">
            {editing
              ? `Editando ${id?.slice(-5).toUpperCase()}`
              : "Nuevo anuncio"}
          </span>
          <h1>{editing ? "Editar habitación" : "Publicar una habitación"}</h1>
        </div>
        <Button
          variant="outline"
          onClick={() => toast.success("Borrador guardado")}
        >
          <Save data-icon="inline-start" />
          Guardar borrador
        </Button>
      </div>
      <div className="container wizard-layout">
        <aside>
          <Stepper steps={steps} current={step} />
        </aside>
        <section className="wizard-content" aria-label="Formulario del anuncio">
          <StepContent step={step} />
          <div className="wizard-actions">
            <Button
              variant="outline"
              disabled={step === 0}
              onClick={() => setStep((value) => value - 1)}
            >
              <ArrowLeft data-icon="inline-start" />
              Atrás
            </Button>
            {step === steps.length - 1 ? (
              <Button onClick={() => setPublished(true)}>
                Enviar a revisión <CheckCircle2 data-icon="inline-end" />
              </Button>
            ) : (
              <Button
                onClick={() => {
                  setStep((value) => value + 1);
                  window.scrollTo({ top: 0, behavior: "smooth" });
                }}
              >
                Continuar <ArrowRight data-icon="inline-end" />
              </Button>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
