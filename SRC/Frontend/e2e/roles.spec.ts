import { expect, test } from '@playwright/test'

const roles = [
  ['fleet@transitops.demo', 'Fleet Manager', 'Is the fleet healthy'],
  ['dispatcher@transitops.demo', 'Dispatcher', 'What needs to move now'],
  ['safety@transitops.demo', 'Safety Officer', 'Which driver, vehicle'],
  ['finance@transitops.demo', 'Financial Analyst', 'Where is money being spent'],
  ['admin@transitops.demo', 'Administrator', 'Is the platform secure'],
] as const

for (const [email, role, question] of roles) {
  test(`${role} receives a scoped dashboard without unauthorized startup requests`, async ({ page }) => {
    const forbidden: string[] = []
    page.on('response', (response) => {
      if (response.status() === 403 && response.url().includes('/api/')) forbidden.push(response.url())
    })
    await page.goto('/')
    await page.getByLabel('Work email').fill(email)
    await page.getByLabel('Password').fill('demo')
    await page.getByRole('button', { name: /sign in/i }).click()
    await expect(page.getByText(role, { exact: true }).first()).toBeVisible()
    await expect(page.getByRole('heading', { name: new RegExp(question, 'i') })).toBeVisible()
    await expect(page.getByText(/Updated/)).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Action Center' })).toBeVisible()
    expect(forbidden).toEqual([])
    if (role === 'Safety Officer') {
      const mobileMenu = page.getByRole('button', { name: 'Open navigation' })
      if (await mobileMenu.isVisible()) await mobileMenu.click()
      await page.getByRole('button', { name: 'Trips' }).click()
      await expect(page.getByRole('button', { name: /New trip/i })).toHaveCount(0)
      await expect(page.getByRole('button', { name: /Dispatch/i })).toHaveCount(0)
    }
    if (role === 'Financial Analyst') {
      await expect(page.getByRole('button', { name: 'Drivers' })).toHaveCount(0)
      await expect(page.getByRole('button', { name: 'Trips' })).toHaveCount(0)
    }
  })
}

test('Driver lands on a useful assignment or empty live-trip state', async ({ page }) => {
  const forbidden: string[] = []
  page.on('response', (response) => {
    if (response.status() === 403 && response.url().includes('/api/')) forbidden.push(response.url())
  })
  await page.goto('/')
  await page.getByLabel('Work email').fill('driver@transitops.demo')
  await page.getByLabel('Password').fill('demo')
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page).toHaveURL(/driver\/live-trip/)
  await expect(page.getByText('My Live Trip', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/No active trip|Live trip|assignment/i).first()).toBeVisible()
  expect(forbidden).toEqual([])
})
