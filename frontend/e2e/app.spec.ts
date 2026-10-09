import { expect, test } from '@playwright/test'

test.describe('App shell', () => {
  test('loads and shows title', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('Developer Docs Chatbot')).toBeVisible()
  })

  test('shows empty-session placeholder by default', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByText('No session selected')).toBeVisible()
  })

  test('Chat and Sources tabs are present', async ({ page }) => {
    await page.goto('/')
    await expect(page.getByRole('button', { name: 'Chat' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Sources' })).toBeVisible()
  })

  test('switching to Sources tab shows the add-source form', async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Sources' }).click()
    await expect(page.getByPlaceholder(/Name/)).toBeVisible()
    await expect(page.getByPlaceholder(/https:\/\//)).toBeVisible()
  })

  test('dark mode toggle switches theme', async ({ page }) => {
    await page.goto('/')
    const html = page.locator('html')
    await expect(html).not.toHaveClass(/dark/)
    await page.getByTitle(/dark mode/i).click()
    await expect(html).toHaveClass(/dark/)
  })
})

// These tests require a running backend (docker compose up)
test.describe('Session management', () => {
  test.beforeEach(async ({ request, page }) => {
    const res = await request.get('http://localhost:8000/sessions').catch(() => null)
    if (!res || !res.ok()) {
      test.skip(true, 'Backend not available')
    }
    await page.goto('/')
  })

  test('+ New button creates a session and opens chat', async ({ page }) => {
    await page.getByRole('button', { name: '+ New' }).click()
    await expect(page.getByPlaceholder(/Ask a question/i)).toBeVisible({ timeout: 10_000 })
  })

  test('created session appears in the sidebar', async ({ page }) => {
    await page.getByRole('button', { name: '+ New' }).click()
    await expect(page.locator('[data-testid="session-item"]').first()).toBeVisible({
      timeout: 10_000,
    })
  })
})

test.describe('Sources panel', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
    await page.getByRole('button', { name: 'Sources' }).click()
  })

  test('shows loading state then resolves', async ({ page }) => {
    // After navigation the panel should not stay on loading indefinitely
    await expect(page.getByText('Loading sources...')).not.toBeVisible({ timeout: 8_000 })
  })

  test('Add button is disabled when form is empty', async ({ page }) => {
    const addBtn = page.getByRole('button', { name: /Add/i })
    await expect(addBtn).toBeDisabled()
  })

  test('Add button enables once both fields filled', async ({ page }) => {
    await page.getByPlaceholder(/Name/).fill('My Docs')
    await page.getByPlaceholder(/https:\/\//).fill('https://docs.example.com/')
    await expect(page.getByRole('button', { name: /Add/i })).toBeEnabled()
  })
})
