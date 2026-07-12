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

test('Fleet manager can use the visual demo entry and open a driver profile', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Use Fleet Manager demo/i }).click()
  await expect(page.getByLabel('Work email')).toHaveValue('fleet@transitops.demo')
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page.getByText('Fleet Manager', { exact: true }).first()).toBeVisible()
  const mobileMenu = page.getByRole('button', { name: 'Open navigation' })
  if (await mobileMenu.isVisible()) await mobileMenu.click()
  await page.getByRole('button', { name: 'Drivers' }).click()
  await expect(page.getByRole('button', { name: /Alex Thomas/i })).toBeVisible()
  await page.getByRole('button', { name: /Alex Thomas/i }).click()
  await expect(page.getByRole('heading', { name: 'Driver profile' })).toBeVisible()
  await expect(page.getByText('Safety rating')).toBeVisible()
})

test('vehicle save errors keep the completed form visible', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: /Use Fleet Manager demo/i }).click()
  await page.getByRole('button', { name: /sign in/i }).click()
  await expect(page.getByText('Fleet Manager', { exact: true }).first()).toBeVisible()
  const mobileMenu = page.getByRole('button', { name: 'Open navigation' })
  if (await mobileMenu.isVisible()) await mobileMenu.click()
  await page.getByRole('button', { name: 'Fleet', exact: true }).click()
  await page.getByRole('button', { name: 'Add vehicle' }).click()
  await page.getByLabel('Registration').fill('GJ 01 AB 1234')
  await page.getByLabel('Vehicle name').fill('Duplicate registration check')
  await page.getByRole('textbox', { name: 'Type' }).fill('Van')
  await page.getByLabel('Capacity (kg)').fill('100')
  await page.getByLabel('Odometer (km)').fill('10')
  await page.getByLabel('Acquisition cost').fill('10000')
  await page.getByRole('button', { name: 'Save record' }).click()
  await expect(page.getByText('A vehicle with this registration already exists.')).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Add vehicle' })).toBeVisible()
  await expect(page.getByLabel('Vehicle name')).toHaveValue('Duplicate registration check')
})
