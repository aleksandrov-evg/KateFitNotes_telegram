export async function chooseOption(control, value) {
  if (await control.evaluate(element => element.tagName === 'SELECT')) return control.selectOption(value);
  await control.click();
  const menu = control.page().locator('#' + await control.getAttribute('aria-controls'));
  for (const option of await menu.getByRole('option').all()) {
    if (await option.getAttribute('data-select-value') === value) return option.click();
  }
  throw new Error('Option not found: ' + value);
}
