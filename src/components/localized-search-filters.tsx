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
import { filterListings } from "@/lib/search";
import type { Filters, RentalMode, YesNoAny } from "@/types";
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

function CheckOption({
  label,
  checked,
  onCheckedChange,
}: {
  label: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <label className="check-option" htmlFor={id}>
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => onCheckedChange(value === true)}
      />
      <span>{label}</span>
    </label>
  );
}

function NativeSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <label className="field-label" htmlFor={id}>
      {label}
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => {
          const item = typeof option === "string" ? { value: option, label: option } : option;
          return <option key={item.value} value={item.value}>{item.label}</option>;
        })}
      </select>
    </label>
  );
}

function YesNoFilter({
  label,
  value,
  onChange,
  language,
}: {
  label: string;
  value: YesNoAny;
  onChange: (value: YesNoAny) => void;
  language: Language;
}) {
  return (
    <NativeSelect
      label={label}
      value={value}
      options={[
        { value: "Cualquiera", label: localize(language, "Cualquiera", "Любой", "Any") },
        { value: "Sí", label: localize(language, "Sí", "Да", "Yes") },
        { value: "No", label: localize(language, "No", "Нет", "No") },
      ]}
      onChange={(next) => onChange(next as YesNoAny)}
    />
  );
}

function NumericInput({
  ariaLabel,
  value,
  min,
  max,
  step = 1,
  onValueChange,
}: {
  ariaLabel: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  onValueChange: (value: number) => void;
}) {
  return (
    <Input
      aria-label={ariaLabel}
      type="number"
      inputMode="numeric"
      min={min}
      max={max}
      step={step}
      value={value}
      onKeyDown={blockInvalidNumberKeys}
      onWheel={(event) => event.currentTarget.blur()}
      onChange={(event) => onValueChange(boundedInteger(event.target.value, min, max))}
    />
  );
}

function FilterPanel({
  value,
  onChange,
  rentalMode,
}: {
  value: Filters;
  onChange: (value: Filters) => void;
  rentalMode: RentalMode;
}) {
  const { language, t } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const update = <K extends keyof Filters>(key: K, next: Filters[K]) =>
    onChange({ ...value, [key]: next });
  const maxPrice = rentalMode === "holiday" ? 350 : 1200;
  const anyLabel = text("Cualquiera", "Любой", "Any");

  const roomTypes: SelectOption[] = [
    { value: "Cualquiera", label: anyLabel },
    { value: "Habitación individual", label: text("Habitación individual", "Отдельная комната", "Private room") },
    { value: "Habitación compartida", label: text("Habitación compartida", "Общая комната", "Shared room") },
    { value: "Estudio", label: text("Estudio", "Студия", "Studio") },
  ];
  const tenantRequirements: SelectOption[] = [
    { value: "Cualquiera", label: anyLabel },
    { value: "single-man", label: text("Solo un hombre", "Только мужчина", "Men only") },
    { value: "single-woman", label: text("Solo una mujer", "Только женщина", "Women only") },
    { value: "single-person", label: text("Una persona", "Один человек", "One person") },
    { value: "couple", label: text("Solo pareja", "Только пара", "Couples only") },
    { value: "any", label: text("Sin restricción", "Без ограничений", "No restriction") },
  ];
  const conditions = [
    { value: "Mascotas permitidas", label: text("Mascotas permitidas", "Можно с животными", "Pets allowed") },
    { value: "No fumar", label: text("No fumar", "Не курить", "No smoking") },
    { value: "Empadronamiento posible", label: text("Empadronamiento posible", "Регистрация возможна", "Registration possible") },
    { value: "Gastos incluidos", label: text("Gastos incluidos", "Расходы включены", "Bills included") },
  ];

  return (
    <div className="filter-panel">
      <label className="field-label filter-room-only">
        {text("Tipo de propiedad", "Тип объекта", "Property type")}
        <select
          aria-label={text("Tipo de propiedad", "Тип объекта", "Property type")}
          value="Habitaciones"
          disabled
        >
          <option>{text("Habitaciones", "Комнаты", "Rooms")}</option>
        </select>
      </label>

      <section className="filter-section">
        <h3>
          {rentalMode === "holiday"
            ? text("Precio por noche", "Цена за ночь", "Price per night")
            : text("Precio por mes", "Цена за месяц", "Price per month")}
        </h3>
        <div className="filter-price-fields">
          <label>
            {text("Desde", "От", "From")}
            <NumericInput
              ariaLabel={text("Precio mínimo", "Минимальная цена", "Minimum price")}
              min={0}
              max={maxPrice}
              step={rentalMode === "holiday" ? 5 : 25}
              value={value.minPrice}
              onValueChange={(next) =>
                onChange({ ...value, minPrice: Math.min(next, value.maxPrice) })
              }
            />
          </label>
          <label>
            {text("Hasta", "До", "To")}
            <NumericInput
              ariaLabel={text("Precio máximo", "Максимальная цена", "Maximum price")}
              min={0}
              max={maxPrice}
              step={rentalMode === "holiday" ? 5 : 25}
              value={value.maxPrice}
              onValueChange={(next) =>
                onChange({ ...value, maxPrice: Math.max(next, value.minPrice) })
              }
            />
          </label>
        </div>
        <div className="range-values">
          <span>{value.minPrice} €</span>
          <span>{value.maxPrice >= maxPrice ? `${maxPrice} €+` : `${value.maxPrice} €`}</span>
        </div>
        <Slider
          min={0}
          max={maxPrice}
          step={rentalMode === "holiday" ? 5 : 25}
          value={[Math.min(value.minPrice, maxPrice), Math.min(value.maxPrice, maxPrice)]}
          onValueChange={([minimum, maximum]) =>
            onChange({ ...value, minPrice: minimum, maxPrice: maximum })
          }
          aria-label={text("Rango de precio", "Диапазон цен", "Price range")}
        />
      </section>

      <Separator />
      <fieldset className="filter-section">
        <legend>{text("Zona", "Район", "Area")}</legend>
        <div className="checks-grid">
          {areas.map((area) => (
            <CheckOption
              key={area}
              label={area}
              checked={value.areas.includes(area)}
              onCheckedChange={(checked) =>
                update("areas", checked ? [...value.areas, area] : value.areas.filter((item) => item !== area))
              }
            />
          ))}
        </div>
      </fieldset>

      <Separator />
      <section className="filter-section">
        <h3>{text("Habitación", "Комната", "Room")}</h3>
        <NativeSelect
          label={text("Tipo", "Тип", "Type")}
          value={value.roomType}
          options={roomTypes}
          onChange={(next) => update("roomType", next)}
        />
        <NativeSelect
          label={text("Requisito para la persona inquilina", "Требования к жильцу", "Tenant requirements")}
          value={value.tenantRequirement}
          options={tenantRequirements}
          onChange={(next) => update("tenantRequirement", next as Filters["tenantRequirement"])}
        />
        <div className="form-grid form-grid--compact">
          <label className="field-label">
            {text("Tamaño mínimo (m²)", "Минимальная площадь (м²)", "Minimum size (m²)")}
            <NumericInput
              ariaLabel={text("Tamaño mínimo (m²)", "Минимальная площадь (м²)", "Minimum size (m²)")}
              min={0}
              max={50}
              value={value.roomSizeMin}
              onValueChange={(next) =>
                onChange({ ...value, roomSizeMin: Math.min(next, value.roomSizeMax) })
              }
            />
          </label>
          <label className="field-label">
            {text("Tamaño máximo (m²)", "Максимальная площадь (м²)", "Maximum size (m²)")}
            <NumericInput
              ariaLabel={text("Tamaño máximo (m²)", "Максимальная площадь (м²)", "Maximum size (m²)")}
              min={1}
              max={50}
              value={value.roomSizeMax}
              onValueChange={(next) =>
                onChange({ ...value, roomSizeMax: Math.max(next, value.roomSizeMin, 1) })
              }
            />
          </label>
        </div>
        <NativeSelect
          label={text("Capacidad de la habitación", "Вместимость комнаты", "Room capacity")}
          value={value.roomCapacity}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "1", label: text("1 persona", "1 человек", "1 person") },
            { value: "2", label: text("2 personas", "2 человека", "2 people") },
          ]}
          onChange={(next) => update("roomCapacity", next)}
        />
      </section>

      <Separator />
      <section className="filter-section">
        <h3>{text("Disponibilidad", "Доступность", "Availability")}</h3>
        <label className="field-label">
          {text("Disponible para esta fecha", "Доступно на выбранную дату", "Available on this date")}
          <Input
            type="date"
            value={value.available}
            onChange={(event) => update("available", event.target.value)}
          />
        </label>
        {rentalMode === "long" ? (
          <NativeSelect
            label={text("Estancia mínima aceptada", "Минимальный срок аренды", "Minimum accepted stay")}
            value={value.minStay}
            options={[
              { value: "Cualquiera", label: anyLabel },
              { value: "1", label: text("1 mes", "1 месяц", "1 month") },
              { value: "2", label: text("2 meses", "2 месяца", "2 months") },
              { value: "3", label: text("3 meses", "3 месяца", "3 months") },
              { value: "6", label: text("6 meses", "6 месяцев", "6 months") },
            ]}
            onChange={(next) => update("minStay", next)}
          />
        ) : (
          <>
            <label className="field-label">
              {text("Estancia mínima: hasta (noches)", "Минимальный срок — не более (ночей)", "Minimum stay up to (nights)")}
              <NumericInput
                ariaLabel={text("Estancia mínima: hasta (noches)", "Минимальный срок — не более (ночей)", "Minimum stay up to (nights)")}
                min={0}
                max={365}
                value={value.minimumNights}
                onValueChange={(next) => update("minimumNights", next)}
              />
            </label>
            <label className="field-label">
              {text("Disponible hasta al menos", "Доступно как минимум до", "Available at least until")}
              <Input
                type="date"
                value={value.availableUntil}
                onChange={(event) => update("availableUntil", event.target.value)}
              />
            </label>
          </>
        )}
        <NativeSelect
          label={text("Publicado", "Опубликовано", "Published")}
          value={value.publicationDate}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "24h", label: text("Últimas 24 horas", "За последние 24 часа", "Last 24 hours") },
            { value: "7d", label: text("Últimos 7 días", "За последние 7 дней", "Last 7 days") },
            { value: "30d", label: text("Últimos 30 días", "За последние 30 дней", "Last 30 days") },
          ]}
          onChange={(next) => update("publicationDate", next)}
        />
      </section>

      <Separator />
      <fieldset className="filter-section">
        <legend>{text("Condiciones destacadas", "Основные условия", "Key conditions")}</legend>
        <div className="checks-grid">
          {conditions.map((condition) => (
            <CheckOption
              key={condition.value}
              label={condition.label}
              checked={value.conditions.includes(condition.value)}
              onCheckedChange={(checked) =>
                update(
                  "conditions",
                  checked
                    ? [...value.conditions, condition.value]
                    : value.conditions.filter((item) => item !== condition.value),
                )
              }
            />
          ))}
        </div>
      </fieldset>

      <Separator />
      <section className="filter-section">
        <h3>{text("Convivencia", "Совместное проживание", "Household")}</h3>
        <YesNoFilter label={text("Se puede fumar", "Можно курить", "Smoking allowed")} value={value.smoking} onChange={(next) => update("smoking", next)} language={language} />
        <YesNoFilter label={text("Mascotas", "Животные", "Pets")} value={value.pets} onChange={(next) => update("pets", next)} language={language} />
        <YesNoFilter label={text("Niños", "Дети", "Children")} value={value.children} onChange={(next) => update("children", next)} language={language} />
        <YesNoFilter label={text("Empadronamiento", "Регистрация", "Registration")} value={value.empadronamiento} onChange={(next) => update("empadronamiento", next)} language={language} />
      </section>

      <Separator />
      <section className="filter-section">
        <h3>{text("Espacios y equipamiento", "Помещения и оснащение", "Spaces and equipment")}</h3>
        <NativeSelect
          label={text("Baño", "Ванная", "Bathroom")}
          value={value.bathroom}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "Baño privado", label: text("Baño privado", "Собственная ванная", "Private bathroom") },
            { value: "Baño compartido", label: text("Baño compartido", "Общая ванная", "Shared bathroom") },
          ]}
          onChange={(next) => update("bathroom", next)}
        />
        <NativeSelect
          label={text("Ducha", "Душ", "Shower")}
          value={value.shower}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "Ducha privada", label: text("Ducha privada", "Собственный душ", "Private shower") },
            { value: "Ducha compartida", label: text("Ducha compartida", "Общий душ", "Shared shower") },
          ]}
          onChange={(next) => update("shower", next)}
        />
        <NativeSelect
          label={text("Cocina", "Кухня", "Kitchen")}
          value={value.kitchen}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "Cocina privada", label: text("Cocina privada", "Собственная кухня", "Private kitchen") },
            { value: "Cocina compartida", label: text("Cocina compartida", "Общая кухня", "Shared kitchen") },
          ]}
          onChange={(next) => update("kitchen", next)}
        />
        <CheckOption label={text("Amueblada", "С мебелью", "Furnished")} checked={value.furnished} onCheckedChange={(checked) => update("furnished", checked)} />
        <CheckOption label={text("Gastos incluidos", "Расходы включены", "Bills included")} checked={value.billsIncluded} onCheckedChange={(checked) => update("billsIncluded", checked)} />
        <div className="checks-grid">
          {amenityOptions.map((amenity) => (
            <CheckOption
              key={amenity}
              label={t(amenity)}
              checked={value.amenities.includes(amenity)}
              onCheckedChange={(checked) =>
                update("amenities", checked ? [...value.amenities, amenity] : value.amenities.filter((item) => item !== amenity))
              }
            />
          ))}
        </div>
      </section>

      <Separator />
      <section className="filter-section">
        <h3>{text("Fianza y vivienda", "Депозит и жильё", "Deposit and household")}</h3>
        <NativeSelect
          label={text("Depósito", "Депозит", "Deposit")}
          value={value.deposit}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "Sin fianza", label: text("Sin fianza", "Без депозита", "No deposit") },
            { value: "Hasta 1 mes", label: text("Hasta 1 mes", "До 1 месяца", "Up to 1 month") },
            { value: "Más de 1 mes", label: text("Más de 1 mes", "Более 1 месяца", "More than 1 month") },
          ]}
          onChange={(next) => update("deposit", next)}
        />
        <NativeSelect
          label={text("Residentes actuales", "Текущие жильцы", "Current residents")}
          value={value.currentResidents}
          options={[
            { value: "Cualquiera", label: anyLabel },
            "1",
            "2",
            "3",
            "4",
            { value: "5+", label: text("5 o más", "5 и более", "5 or more") },
          ]}
          onChange={(next) => update("currentResidents", next)}
        />
        <NativeSelect
          label={text("Tipo de anunciante", "Тип арендодателя", "Advertiser type")}
          value={value.advertiserType}
          options={[
            { value: "Cualquiera", label: anyLabel },
            { value: "Particular", label: text("Particular", "Частное лицо", "Private advertiser") },
            { value: "Profesional", label: text("Profesional", "Профессионал", "Professional") },
          ]}
          onChange={(next) => update("advertiserType", next)}
        />
      </section>
    </div>
  );
}

export function FilterButton({
  resultCount,
  onFiltersChange,
  onRentalModeChange,
}: {
  resultCount: number;
  onFiltersChange?: (filters: Filters) => void;
  onRentalModeChange?: (mode: RentalMode) => void;
}) {
  const {
    filters,
    setFilters,
    activeFilterCount,
    rentalMode,
    allListings,
    discarded,
  } = useApp();
  const { language } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const [draft, setDraft] = useState(filters);
  const [open, setOpen] = useState(false);
  const draftResultCount = useMemo(
    () => filterListings(
      allListings.filter((item) => !discarded.has(item.id)),
      rentalMode,
      draft,
    ).length,
    [allListings, discarded, draft, rentalMode],
  );

  useEffect(() => {
    if (open) setDraft(filters);
  }, [open, filters]);

  const commit = onFiltersChange ?? setFilters;
  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          aria-label={text(
            `Todos los filtros. ${resultCount} habitaciones actuales`,
            `Все фильтры. Сейчас комнат: ${resultCount}`,
            `All filters. ${resultCount} rooms currently`,
          )}
        >
          <SlidersHorizontal data-icon="inline-start" />
          {text("Filtros", "Фильтры", "Filters")}
          {activeFilterCount ? <span className="filter-count">{activeFilterCount}</span> : null}
        </Button>
      </SheetTrigger>
      <SheetContent className="filter-drawer" showCloseButton={false}>
        <SheetHeader>
          <SheetClose asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="filter-drawer__back"
              aria-label={text("Cerrar filtros", "Закрыть фильтры", "Close filters")}
            >
              <X />
            </Button>
          </SheetClose>
          <SheetTitle>{text("Filtros", "Фильтры", "Filters")}</SheetTitle>
          <SheetDescription>
            {text(
              "Ajusta las condiciones y revisa cuántas habitaciones coinciden.",
              "Настройте условия и проверьте количество подходящих комнат.",
              "Adjust the conditions and check how many rooms match.",
            )}
          </SheetDescription>
        </SheetHeader>
        {onRentalModeChange ? (
          <div className="filter-mode-switch">
            <span>{text("Tipo de estancia", "Тип аренды", "Stay type")}</span>
            <RentalTypeSwitch compact onChange={onRentalModeChange} />
          </div>
        ) : null}
        <FilterPanel value={draft} onChange={setDraft} rentalMode={rentalMode} />
        <SheetFooter className="filter-footer">
          <Button
            variant="ghost"
            onClick={() => setDraft({ ...defaultFilters })}
          >
            {text("Limpiar", "Сбросить", "Clear")}
          </Button>
          <Button
            onClick={() => {
              commit(draft);
              setOpen(false);
            }}
          >
            {text(
              `Mostrar ${draftResultCount} habitaciones`,
              `Показать: ${roomCount(language, draftResultCount)}`,
              `Show ${roomCount(language, draftResultCount)}`,
            )}
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
}

export function FilterSidebar({
  resultCount,
  onFiltersChange,
}: {
  resultCount: number;
  onFiltersChange?: (filters: Filters) => void;
}) {
  const {
    filters,
    setFilters,
    activeFilterCount,
    saveCurrentSearch,
    rentalMode,
  } = useApp();
  const { language } = useI18n();
  const text = (es: string, ru: string, en: string) => localize(language, es, ru, en);
  const commit = onFiltersChange ?? setFilters;

  return (
    <aside
      className="filter-sidebar"
      aria-label={text("Filtros de búsqueda", "Фильтры поиска", "Search filters")}
    >
      <div className="filter-sidebar__save">
        <Button className="w-full" onClick={saveCurrentSearch}>
          <Heart data-icon="inline-start" />
          {text("Guardar búsqueda", "Сохранить поиск", "Save search")}
        </Button>
        <p>{text("Recibe avisos cuando haya habitaciones nuevas.", "Получайте уведомления о новых комнатах.", "Get alerts when new rooms appear.")}</p>
      </div>
      <div className="filter-sidebar__head">
        <h2>{text("Filtrar resultados", "Фильтровать результаты", "Filter results")}</h2>
        {activeFilterCount ? (
          <button type="button" onClick={() => commit({ ...defaultFilters })}>
            {text(`Borrar (${activeFilterCount})`, `Сбросить (${activeFilterCount})`, `Clear (${activeFilterCount})`)}
          </button>
        ) : null}
      </div>
      <FilterPanel value={filters} onChange={commit} rentalMode={rentalMode} />
      <div className="filter-sidebar__result" aria-live="polite">
        {roomCount(language, resultCount)}
      </div>
    </aside>
  );
}
