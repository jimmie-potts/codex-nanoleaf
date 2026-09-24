// Opens or closes the wall's Options menu the way a user would: through its summary control.
const menu = page => page.locator('#wallOptions');
module.exports = {
  async open(page) {
    if (await menu(page).count() && !await menu(page).evaluate(node => node.open)) await page.locator('#wallOptions > summary').click();
  },
  async close(page) {
    if (await menu(page).count() && await menu(page).evaluate(node => node.open)) await page.locator('#wallOptions > summary').click();
  },
};
