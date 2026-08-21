import { useEffect, useId, useMemo, useState, type KeyboardEvent } from "react";
import { Heart, SlidersHorizontal, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Slider } from "@/components/ui/slider";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { amenityOptions, areas, defaultFilters } from "@/data/listings";
import { useApp } from "@/contexts/app-context";
import { useI18n, type Language } from "@/contexts/i18n-context";
import { bedTypeLabel } from "@/lib/bed-type-label";
import { filterListings } from "@/lib/search";
import { priceControlValues } from "@/lib/price-filter-controls";
import type { AcceptedTenantType, Filters, RentalMode, YesNoAny } from "@/types";
import { RentalTypeSwitch } from "./marketplace";

type SelectOption = string | { value: string; label: string };

function localize(language: Language, es: string, ru: string, en: string) {
  if (language === "ru") return ru;
  if (language === "en") return en;
  return es;
}

function roomCount(language: Language, count: number) {
  if (language === "es") return `${count} ${count === 1 ? "habitación" : "habitaciones"}`;
  if (language === "en") return `${count} ${count === 1 ? "room" : "rooms"}`;
  const mod10 = count % 10;
  const mod100 = count % 100;
  const noun = mod10 === 1 && mod100 !== 11
    ? "комната"
    : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
      ? "комнаты"
      : "комнат";
  return `${count} ${noun}`;
}

function boundedInteger(rawValue: string, min: number, max: number) {
  const digits = rawValue.replace(/[^0-9]/g, "");
  if (!digits) return min;
  const value = Number(digits);
  if (!Number.isFinite(value)) return min;
  return Math.min(max, Math.max(min, Math.round(value)));
}

function blockInvalidNumberKeys(event: KeyboardEvent<HTMLInputElement>) {
  if (["e", "E", "+", "-", ".", ","].includes(event.key)) event.preventDefault();
}

function CheckOption({ label, checked, onCheckedChange }: { label: string; checked: boolean; onCheckedChange: (checked: boolean) => void }) {
  const id = useId();
  return <label className="check-option" htmlFor={id}><Checkbox id={id} checked={checked} onCheckedChange={(value) => onCheckedChange(value === true)} /><span>{label}</span></label>;
}

function NativeSelect({ label, value, options, onChange }: { label: string; value: string; options: SelectOption[]; onChange: (value: string) => void }) {
  const id = useId();
  return <label className="field-label" htmlFor={id}>{label}<select id={id} value={value} onChange={(event) => onChange(event.target.value)}>{options.map((option) => { const item = typeof option === "string" ? { value: option, label: option } : option; return <option key={item.value} value={item.value}>{item.label}</option>; })}</select></label>;
}

function YesNoFilter({ label, value, onChange, language }: { label: string; value: YesNoAny; onChange: (value: YesNoAny) => void; language: Language }) {
  return <NativeSelect label={label} value={value} options={[
    { value: "Cualquiera", label: localize(language, "Cualquiera", "Любой", "Any") },
    { value: "Sí", label: localize(language, "Sí", "Да", "Yes") },
    { value: "No", label: localize(language, "No", "Нет", "No") },
  ]} onChange={(next) => onChange(next as YesNoAny)} />;
}

function NumericInput({ ariaLabel, value, min, max, step = 1, onValueChange }: { ariaLabel: string; value: number; min: number; max: number; step?: number; onValueChange: (value: number) => void }) {
  return <Input aria-label={ariaLabel} type="number" inputMode="numeric" min={min} max={max} step={step} value={value} onKeyDown={blockInvalidNumberKeys} onWheel={(event) => event.currentTarget.blur()} onChange={(event) => onValueChange(boundedInteger(event.target.value, min, max))} />;
}

function FilterPanel({ value, onChange, rentalMode }: { value: Filters; onChange: (value: Filters) => void; rentalMode: RentalMode }) {
  const { language, t } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const update = <K extends keyof Filters>(key: K, next: Filters[K]) => onChange({ ...value, [key]: next });
  const maxPrice = rentalMode === "holiday" ? 350 : 1200;
  const priceControls = priceControlValues(value, rentalMode);
  const anyLabel = text("Cualquiera", "Любой", "Any");
  const capacityOptions: SelectOption[] = [{ value: "Cualquiera", label: anyLabel }, ...Array.from({ length: 10 }, (_, index) => ({ value: String(index + 1), label: text(`${index + 1} ${index === 0 ? "persona" : "personas"}`, `${index + 1} чел.`, `${index + 1} ${index === 0 ? "person" : "people"}`) }))];
  const tenantRequirements: SelectOption[] = [
    { value: "Cualquiera", label: anyLabel },
    { value: "single-man", label: text("Solo un hombre", "Только мужчина", "One man only") },
    { value: "single-woman", label: text("Solo una mujer", "Только женщина", "One woman only") },
    { value: "single-person", label: text("Una persona", "Один человек", "One person") },
    { value: "couple", label: text("Solo pareja", "Только пара", "Couple only") },
    { value: "any", label: text("Sin restricción", "Без ограничений", "No restriction") },
  ];
  const acceptedTenantOptions: Array<{ value: AcceptedTenantType; es: string; ru: string; en: string }> = [
    { value: "man", es: "Acepta hombres", ru: "Можно мужчинам", en: "Men accepted" },
    { value: "woman", es: "Acepta mujeres", ru: "Можно женщинам", en: "Women accepted" },
    { value: "couple", es: "Acepta parejas", ru: "Можно парам", en: "Couples accepted" },
    { value: "family", es: "Acepta familias", ru: "Можно семьям", en: "Families accepted" },
  ];
  const conditions = [
    { value: "Mascotas permitidas", label: text("Mascotas permitidas", "Можно с животными", "Pets allowed") },
    { value: "No fumar", label: text("No fumar", "Не курить", "No smoking") },
    { value: "Empadronamiento posible", label: text("Empadronamiento posible", "Регистрация возможна", "Registration possible") },
    { value: "Gastos incluidos", label: text("Gastos incluidos", "Расходы включены", "Bills included") },
  ];

  return <div className="filter-panel">
    <label className="field-label filter-room-only">{text("Tipo de propiedad", "Тип объекта", "Property type")}<select aria-label={text("Tipo de propiedad", "Тип объекта", "Property type")} value="Habitaciones" disabled><option>{text("Habitaciones", "Комнаты", "Rooms")}</option></select></label>

    <section className="filter-section"><h3>{rentalMode === "holiday" ? text("Precio por noche", "Цена за ночь", "Price per night") : text("Precio por mes", "Цена за месяц", "Price per month")}</h3>
      <div className="filter-price-fields"><label>{text("Desde", "От", "From")}<NumericInput ariaLabel={text("Precio mínimo", "Минимальная цена", "Minimum price")} min={0} max={maxPrice} step={rentalMode === "holiday" ? 5 : 25} value={priceControls.minimum} onValueChange={(next) => onChange({ ...value, minPrice: Math.min(next, priceControls.maximum) })} /></label><label>{text("Hasta", "До", "To")}<NumericInput ariaLabel={text("Precio máximo", "Максимальная цена", "Maximum price")} min={0} max={maxPrice} step={rentalMode === "holiday" ? 5 : 25} value={priceControls.maximum} onValueChange={(next) => onChange({ ...value, minPrice: Math.min(priceControls.minimum, next), maxPrice: Math.max(next, priceControls.minimum) })} /></label></div>
      <div className="range-values"><span>{priceControls.minimum} €</span><span>{priceControls.maximum >= maxPrice ? `${maxPrice} €+` : `${priceControls.maximum} €`}</span></div>
      <Slider min={0} max={maxPrice} step={rentalMode === "holiday" ? 5 : 25} value={[priceControls.minimum, priceControls.maximum]} onValueChange={([minimum, maximum]) => onChange({ ...value, minPrice: minimum, maxPrice: maximum })} aria-label={text("Rango de precio", "Диапазон цен", "Price range")} />
    </section>

    <Separator />
    <fieldset className="filter-section"><legend>{text("Zona", "Район", "Area")}</legend><div className="checks-grid">{areas.map((area) => <CheckOption key={area} label={area} checked={value.areas.includes(area)} onCheckedChange={(checked) => update("areas", checked ? [...value.areas, area] : value.areas.filter((item) => item !== area))} />)}</div></fieldset>

    <Separator />
    <section className="filter-section"><h3>{text("Habitación", "Комната", "Room")}</h3>
      <NativeSelect label={text("Tipo de habitación", "Тип комнаты", "Room type")} value={value.roomType} options={[
        { value: "Cualquiera", label: anyLabel },
        { value: "Habitación individual", label: text("Habitación privada", "Отдельная комната", "Private room") },
        { value: "Habitación compartida", label: text("Habitación compartida", "Общая комната", "Shared room") },
        { value: "Estudio", label: text("Estudio", "Студия", "Studio") },
      ]} onChange={(next) => update("roomType", next)} />
      <NativeSelect label={text("Qué se alquila", "Что сдаётся", "Rental unit")} value={value.rentalUnit} options={[{ value: "Cualquiera", label: anyLabel }, { value: "room", label: text("Habitación completa", "Комната целиком", "Whole room") }, { value: "bed", label: text("Plaza / cama", "Спальное место", "Bed space") }]} onChange={(next) => update("rentalUnit", next as Filters["rentalUnit"])} />
      <NativeSelect label={text("Tipo de cama", "Тип кровати", "Bed type")} value={value.bedType} options={[{ value: "Cualquiera", label: anyLabel }, { value: "single", label: bedTypeLabel(language, 'single') }, { value: "double", label: bedTypeLabel(language, 'double') }, { value: "bunk", label: bedTypeLabel(language, 'bunk') }]} onChange={(next) => update("bedType", next as Filters["bedType"])} />
      <label className="field-label">{text("Mínimo de camas", "Минимум кроватей", "Minimum beds")}<NumericInput ariaLabel={text("Mínimo de camas", "Минимум кроватей", "Minimum beds")} min={0} max={10} value={value.bedCountMin} onValueChange={(next) => update("bedCountMin", next)} /></label>
      <NativeSelect label={text("Capacidad de la habitación", "Вместимость комнаты", "Room capacity")} value={value.roomCapacity} options={capacityOptions} onChange={(next) => update("roomCapacity", next)} />
      <NativeSelect label={text("Ya viven en esta habitación", "Уже живут в комнате", "Already in this room")} value={value.roomResidents} options={[{ value: "Cualquiera", label: anyLabel }, ...Array.from({ length: 10 }, (_, i) => String(i))]} onChange={(next) => update("roomResidents", next)} />
      <label className="field-label">{text("Plazas libres mínimas", "Минимум свободных мест", "Minimum free spaces")}<NumericInput ariaLabel={text("Plazas libres mínimas", "Минимум свободных мест", "Minimum free spaces")} min={0} max={10} value={value.availableSpotsMin} onValueChange={(next) => update("availableSpotsMin", next)} /></label>
    </section>

    <Separator />
    <section className="filter-section"><h3>{text("Disponibilidad", "Доступность", "Availability")}</h3>
      <label className="field-label">{text("Disponible para esta fecha", "Доступно на дату", "Available for this date")}<Input aria-label={text("Disponible para esta fecha", "Доступно на дату", "Available for this date")} type="date" value={value.available} onChange={(event) => update("available", event.target.value)} /></label>
      <label className="field-label">{text("Disponible hasta al menos", "Доступно как минимум до", "Available until at least")}<Input aria-label={text("Disponible hasta al menos", "Доступно как минимум до", "Available until at least")} type="date" value={value.availableUntil} onChange={(event) => update("availableUntil", event.target.value)} /></label>
      {rentalMode === "long" ? <NativeSelect label={text("Estancia mínima aceptada", "Допустимый минимальный срок", "Accepted minimum stay")} value={value.minStay} options={[{ value: "Cualquiera", label: anyLabel }, { value: "1", label: text("1 mes", "1 месяц", "1 month") }, { value: "2", label: text("2 meses", "2 месяца", "2 months") }, { value: "3", label: text("3 meses", "3 месяца", "3 months") }, { value: "6", label: text("6 meses", "6 месяцев", "6 months") }, { value: "12", label: text("12 meses", "12 месяцев", "12 months") }]} onChange={(next) => update("minStay", next)} /> : <label className="field-label">{text("Estancia mínima: hasta (noches)", "Минимальный срок — не более (ночей)", "Minimum stay up to (nights)")}<NumericInput ariaLabel={text("Estancia mínima: hasta (noches)", "Минимальный срок — не более (ночей)", "Minimum stay up to (nights)")} min={0} max={365} value={value.minimumNights} onValueChange={(next) => update("minimumNights", next)} /></label>}
      <NativeSelect label={text("Publicado", "Опубликовано", "Published")} value={value.publicationDate} options={[{ value: "Cualquiera", label: anyLabel }, { value: "24h", label: text("Últimas 24 horas", "За последние 24 часа", "Last 24 hours") }, { value: "7d", label: text("Últimos 7 días", "За последние 7 дней", "Last 7 days") }, { value: "30d", label: text("Últimos 30 días", "За последние 30 дней", "Last 30 days") }]} onChange={(next) => update("publicationDate", next)} />
    </section>

    <Separator />
    <fieldset className="filter-section"><legend>{text("Condiciones destacadas", "Основные условия", "Highlighted conditions")}</legend><div className="checks-grid">{conditions.map((condition) => <CheckOption key={condition.value} label={condition.label} checked={value.conditions.includes(condition.value)} onCheckedChange={(checked) => update("conditions", checked ? [...value.conditions, condition.value] : value.conditions.filter((item) => item !== condition.value))} />)}</div></fieldset>

    <Separator />
    <section className="filter-section"><h3>{text("Vivienda y convivencia", "Квартира и жильцы", "Home and household")}</h3>
      <div className="form-grid form-grid--compact"><label className="field-label">{text("Vivienda desde (m²)", "Площадь жилья от (м²)", "Home size from (m²)")}<NumericInput ariaLabel={text("Vivienda desde", "Площадь жилья от", "Home size from")} min={0} max={500} value={value.homeSizeMin} onValueChange={(next) => onChange({ ...value, homeSizeMin: Math.min(next, value.homeSizeMax) })} /></label><label className="field-label">{text("Vivienda hasta (m²)", "Площадь жилья до (м²)", "Home size to (m²)")}<NumericInput ariaLabel={text("Vivienda hasta", "Площадь жилья до", "Home size to")} min={1} max={500} value={value.homeSizeMax} onValueChange={(next) => onChange({ ...value, homeSizeMax: Math.max(next, value.homeSizeMin, 1) })} /></label></div>
      <label className="field-label">{text("Baños en la vivienda: mínimo", "Санузлов в жилье: минимум", "Bathrooms in home: minimum")}<NumericInput ariaLabel={text("Mínimo de baños", "Минимум санузлов", "Minimum bathrooms")} min={0} max={20} value={value.bathroomCountMin} onValueChange={(next) => update("bathroomCountMin", next)} /></label>
      <NativeSelect label={text("Residentes actuales", "Сейчас живут", "Current residents")} value={value.currentResidents} options={[{ value: "Cualquiera", label: anyLabel }, "0", "1", "2", "3", "4", { value: "5+", label: text("5 o más", "5 и более", "5 or more") }]} onChange={(next) => update("currentResidents", next)} />
      <NativeSelect label={text("Composición de la vivienda", "Состав жильцов", "Household composition")} value={value.householdGender} options={[{ value: "Cualquiera", label: anyLabel }, { value: "men", label: text("Hombres", "Мужчины", "Men") }, { value: "women", label: text("Mujeres", "Женщины", "Women") }, { value: "mixed", label: text("Mixto", "Совместное проживание", "Mixed") }]} onChange={(next) => update("householdGender", next as Filters["householdGender"])} />
      <YesNoFilter label={text("Hay niños en la vivienda", "В квартире есть дети", "Children live in the home")} value={value.householdHasChildren} onChange={(next) => update("householdHasChildren", next)} language={language} />
    </section>

    <Separator />
    <section className="filter-section"><h3>{text("Espacios y equipamiento", "Помещения и оснащение", "Spaces and equipment")}</h3>
      <NativeSelect label={text("Baño", "Ванная", "Bathroom")} value={value.bathroom} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Baño privado", label: text("Baño privado", "Собственная ванная", "Private bathroom") }, { value: "Baño compartido", label: text("Baño compartido", "Общая ванная", "Shared bathroom") }]} onChange={(next) => update("bathroom", next)} />
      <NativeSelect label={text("Aseo / WC", "Туалет", "Toilet")} value={value.toilet} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Aseo privado", label: text("Aseo privado", "Собственный туалет", "Private toilet") }, { value: "Aseo compartido", label: text("Aseo compartido", "Общий туалет", "Shared toilet") }]} onChange={(next) => update("toilet", next)} />
      <NativeSelect label={text("Ducha", "Душ", "Shower")} value={value.shower} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Ducha privada", label: text("Ducha privada", "Собственный душ", "Private shower") }, { value: "Ducha compartida", label: text("Ducha compartida", "Общий душ", "Shared shower") }]} onChange={(next) => update("shower", next)} />
      <NativeSelect label={text("Cocina", "Кухня", "Kitchen")} value={value.kitchen} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Cocina privada", label: text("Cocina privada", "Собственная кухня", "Private kitchen") }, { value: "Cocina compartida", label: text("Cocina compartida", "Общая кухня", "Shared kitchen") }]} onChange={(next) => update("kitchen", next)} />
      <NativeSelect label={text("Calefacción", "Отопление", "Heating")} value={value.heatingType} options={[{ value: "Cualquiera", label: anyLabel }, { value: "individual", label: text("Individual", "Индивидуальное", "Individual") }, { value: "central", label: text("Central", "Центральное", "Central") }, { value: "none", label: text("Sin calefacción", "Нет отопления", "No heating") }]} onChange={(next) => update("heatingType", next as Filters["heatingType"])} />
      <YesNoFilter label={text("Adaptada para movilidad reducida", "Адаптировано для маломобильных", "Accessible")} value={value.accessible} onChange={(next) => update("accessible", next)} language={language} />
      <NativeSelect label={text("Planta", "Этаж", "Floor")} value={value.floor} options={[{ value: "Cualquiera", label: anyLabel }, { value: "basement", label: text("Sótano / semisótano", "Цокольный", "Basement") }, "1", "2", "3", { value: "4+", label: "4+" }, { value: "top", label: text("Última planta", "Последний этаж", "Top floor") }]} onChange={(next) => update("floor", next as Filters["floor"])} />
      <CheckOption label={text("Amueblada", "С мебелью", "Furnished")} checked={value.furnished} onCheckedChange={(checked) => update("furnished", checked)} />
      <CheckOption label={text("Gastos incluidos", "Расходы включены", "Bills included")} checked={value.billsIncluded} onCheckedChange={(checked) => update("billsIncluded", checked)} />
      <div className="checks-grid">{amenityOptions.filter((amenity) => amenity !== "Aire acondicionado").map((amenity) => <CheckOption key={amenity} label={t(amenity)} checked={value.amenities.includes(amenity)} onCheckedChange={(checked) => update("amenities", checked ? [...value.amenities, amenity] : value.amenities.filter((item) => item !== amenity))} />)}</div>
    </section>

    <Separator />
    <section className="filter-section"><h3>{text("Quién puede alojarse", "Кого принимают", "Who can stay")}</h3>
      <NativeSelect label={text("Requisito para la persona inquilina", "Требование к арендатору", "Tenant requirement")} value={value.tenantRequirement} options={tenantRequirements} onChange={(next) => update("tenantRequirement", next as Filters["tenantRequirement"])} />
      <div className="checks-grid">{acceptedTenantOptions.map((option) => <CheckOption key={option.value} label={text(option.es, option.ru, option.en)} checked={value.acceptedTenantTypes.includes(option.value)} onCheckedChange={(checked) => update("acceptedTenantTypes", checked ? [...value.acceptedTenantTypes, option.value] : value.acceptedTenantTypes.filter((item) => item !== option.value))} />)}</div>
      <YesNoFilter label={text("Parejas permitidas", "Можно парам", "Couples allowed")} value={value.couplesAllowed} onChange={(next) => update("couplesAllowed", next)} language={language} />
      <YesNoFilter label={text("Niños", "Дети", "Children")} value={value.children} onChange={(next) => update("children", next)} language={language} />
      <YesNoFilter label={text("Mascotas", "Животные", "Pets")} value={value.pets} onChange={(next) => update("pets", next)} language={language} />
      <YesNoFilter label={text("Se puede fumar", "Можно курить", "Smoking allowed")} value={value.smoking} onChange={(next) => update("smoking", next)} language={language} />
      <YesNoFilter label={text("Empadronamiento", "Регистрация", "Registration")} value={value.empadronamiento} onChange={(next) => update("empadronamiento", next)} language={language} />
    </section>

    <Separator />
    <section className="filter-section"><h3>{text("Fianza y anunciante", "Депозит и арендодатель", "Deposit and advertiser")}</h3>
      <NativeSelect label={text("Depósito", "Депозит", "Deposit")} value={value.deposit} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Sin fianza", label: text("Sin fianza", "Без депозита", "No deposit") }, { value: "Hasta 1 mes", label: text("Hasta 1 mes", "До 1 месяца", "Up to 1 month") }, { value: "Más de 1 mes", label: text("Más de 1 mes", "Более 1 месяца", "More than 1 month") }]} onChange={(next) => update("deposit", next)} />
      <NativeSelect label={text("Tipo de anunciante", "Тип арендодателя", "Advertiser type")} value={value.advertiserType} options={[{ value: "Cualquiera", label: anyLabel }, { value: "Particular", label: text("Particular", "Частное лицо", "Private advertiser") }, { value: "Profesional", label: text("Profesional", "Профессионал", "Professional") }]} onChange={(next) => update("advertiserType", next)} />
    </section>
  </div>;
}

export function FilterButton({ resultCount, onFiltersChange, onRentalModeChange }: { resultCount: number; onFiltersChange?: (filters: Filters) => void; onRentalModeChange?: (mode: RentalMode) => void }) {
  const { filters, setFilters, activeFilterCount, rentalMode, allListings, discarded } = useApp();
  const { language } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const [draft, setDraft] = useState(filters);
  const [open, setOpen] = useState(false);
  const draftResultCount = useMemo(() => filterListings(allListings.filter((item) => !discarded.has(item.id)), rentalMode, draft).length, [allListings, discarded, draft, rentalMode]);
  useEffect(() => { if (open) setDraft(filters); }, [open, filters]);
  const commit = onFiltersChange ?? setFilters;
  return <Sheet open={open} onOpenChange={setOpen}><SheetTrigger asChild><Button variant="outline" aria-label={text(`Todos los filtros. ${resultCount} habitaciones actuales`, `Все фильтры. Сейчас комнат: ${resultCount}`, `All filters. ${resultCount} rooms currently`)}><SlidersHorizontal data-icon="inline-start" />{text("Filtros", "Фильтры", "Filters")}{activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}</Button></SheetTrigger><SheetContent className="filter-drawer" showCloseButton={false}><SheetHeader><SheetClose asChild><Button type="button" variant="ghost" size="icon" className="filter-drawer__back" aria-label={text("Cerrar filtros", "Закрыть фильтры", "Close filters")}><X /></Button></SheetClose><SheetTitle>{text("Filtros", "Фильтры", "Filters")}</SheetTitle><SheetDescription>{text("Filtra por habitación, plazas, vivienda, convivencia y disponibilidad.", "Фильтруйте по комнате, местам, квартире, жильцам и датам.", "Filter by room, spaces, home, household and availability.")}</SheetDescription></SheetHeader>{onRentalModeChange ? <div className="filter-mode-switch"><span>{text("Tipo de estancia", "Тип аренды", "Stay type")}</span><RentalTypeSwitch compact onChange={onRentalModeChange} /></div> : null}<FilterPanel value={draft} onChange={setDraft} rentalMode={rentalMode} /><SheetFooter className="filter-footer"><Button variant="ghost" onClick={() => setDraft({ ...defaultFilters, areas: [], conditions: [], tenantRequirements: [], acceptedTenantTypes: [], amenities: [] })}>{text("Limpiar", "Сбросить", "Clear")}</Button><Button onClick={() => { commit(draft); setOpen(false); }}>{text(`Mostrar ${draftResultCount} habitaciones`, `Показать: ${roomCount(language, draftResultCount)}`, `Show ${roomCount(language, draftResultCount)}`)}</Button></SheetFooter></SheetContent></Sheet>;
}

export function FilterSidebar({ resultCount, onFiltersChange }: { resultCount: number; onFiltersChange?: (filters: Filters) => void }) {
  const { filters, setFilters, activeFilterCount, saveCurrentSearch, rentalMode } = useApp();
  const { language } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const commit = onFiltersChange ?? setFilters;
  return <aside className="filter-sidebar" aria-label={text("Filtros de búsqueda", "Фильтры поиска", "Search filters")}><div className="filter-sidebar__save"><Button className="w-full" onClick={saveCurrentSearch}><Heart data-icon="inline-start" />{text("Guardar búsqueda", "Сохранить поиск", "Save search")}</Button><p>{text("Recibe avisos cuando haya habitaciones nuevas que encajen.", "Получайте уведомления о новых подходящих комнатах.", "Get alerts when matching rooms appear.")}</p></div><div className="filter-sidebar__head"><h2>{text("Filtrar resultados", "Фильтровать результаты", "Filter results")}</h2>{activeFilterCount ? <button type="button" onClick={() => commit({ ...defaultFilters, areas: [], conditions: [], tenantRequirements: [], acceptedTenantTypes: [], amenities: [] })}>{text(`Borrar (${activeFilterCount})`, `Сбросить (${activeFilterCount})`, `Clear (${activeFilterCount})`)}</button> : null}</div><FilterPanel value={filters} onChange={commit} rentalMode={rentalMode} /><div className="filter-sidebar__result" aria-live="polite">{roomCount(language, resultCount)}</div></aside>;
}
