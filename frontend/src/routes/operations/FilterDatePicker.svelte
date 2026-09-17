<script lang="ts">
  import { DatePicker, Portal, parseDate, type DateValue } from '@skeletonlabs/skeleton-svelte';

  let { id, value = $bindable('') }: { id: string; value?: string } = $props();

  function toDateValue(raw: string): DateValue | undefined {
    if (!raw) return undefined;
    try {
      return parseDate(raw.slice(0, 10));
    } catch {
      return undefined;
    }
  }

  const selected = $derived.by<DateValue[] | undefined>(() => {
    const date = toDateValue(value);
    return date ? [date] : undefined;
  });
</script>

<DatePicker
  value={selected}
  onValueChange={(details) => {
    value = details.valueAsString[0] ?? '';
  }}
>
  <DatePicker.Control>
    <DatePicker.Input id={id} class="input" placeholder="yyyy-mm-dd" data-testid={`${id}-input`} />
    <DatePicker.Trigger class="btn preset-tonal" />
  </DatePicker.Control>
  <Portal>
    <DatePicker.Positioner>
      <DatePicker.Content class="z-50">
        <DatePicker.View view="day">
          <DatePicker.Context>
            {#snippet children(datePicker)}
              <DatePicker.ViewControl>
                <DatePicker.PrevTrigger />
                <DatePicker.ViewTrigger><DatePicker.RangeText /></DatePicker.ViewTrigger>
                <DatePicker.NextTrigger />
              </DatePicker.ViewControl>
              <DatePicker.Table>
                <DatePicker.TableHead>
                  <DatePicker.TableRow>
                    {#each datePicker().weekDays as weekDay, index (index)}
                      <DatePicker.TableHeader>{weekDay.short}</DatePicker.TableHeader>
                    {/each}
                  </DatePicker.TableRow>
                </DatePicker.TableHead>
                <DatePicker.TableBody>
                  {#each datePicker().weeks as week, weekIndex (weekIndex)}
                    <DatePicker.TableRow>
                      {#each week as day, dayIndex (dayIndex)}
                        <DatePicker.TableCell value={day}>
                          <DatePicker.TableCellTrigger>{day.day}</DatePicker.TableCellTrigger>
                        </DatePicker.TableCell>
                      {/each}
                    </DatePicker.TableRow>
                  {/each}
                </DatePicker.TableBody>
              </DatePicker.Table>
            {/snippet}
          </DatePicker.Context>
        </DatePicker.View>
        <DatePicker.View view="month">
          <DatePicker.Context>
            {#snippet children(datePicker)}
              <DatePicker.ViewControl>
                <DatePicker.PrevTrigger />
                <DatePicker.ViewTrigger><DatePicker.RangeText /></DatePicker.ViewTrigger>
                <DatePicker.NextTrigger />
              </DatePicker.ViewControl>
              <DatePicker.Table>
                <DatePicker.TableBody>
                  {#each datePicker().getMonthsGrid({ columns: 4, format: 'short' }) as months, monthIndex (monthIndex)}
                    <DatePicker.TableRow>
                      {#each months as month, index (index)}
                        <DatePicker.TableCell value={month.value}>
                          <DatePicker.TableCellTrigger>{month.label}</DatePicker.TableCellTrigger>
                        </DatePicker.TableCell>
                      {/each}
                    </DatePicker.TableRow>
                  {/each}
                </DatePicker.TableBody>
              </DatePicker.Table>
            {/snippet}
          </DatePicker.Context>
        </DatePicker.View>
        <DatePicker.View view="year">
          <DatePicker.Context>
            {#snippet children(datePicker)}
              <DatePicker.ViewControl>
                <DatePicker.PrevTrigger />
                <DatePicker.ViewTrigger><DatePicker.RangeText /></DatePicker.ViewTrigger>
                <DatePicker.NextTrigger />
              </DatePicker.ViewControl>
              <DatePicker.Table>
                <DatePicker.TableBody>
                  {#each datePicker().getYearsGrid({ columns: 4 }) as years, yearIndex (yearIndex)}
                    <DatePicker.TableRow>
                      {#each years as year, index (index)}
                        <DatePicker.TableCell value={year.value}>
                          <DatePicker.TableCellTrigger>{year.label}</DatePicker.TableCellTrigger>
                        </DatePicker.TableCell>
                      {/each}
                    </DatePicker.TableRow>
                  {/each}
                </DatePicker.TableBody>
              </DatePicker.Table>
            {/snippet}
          </DatePicker.Context>
        </DatePicker.View>
      </DatePicker.Content>
    </DatePicker.Positioner>
  </Portal>
</DatePicker>
