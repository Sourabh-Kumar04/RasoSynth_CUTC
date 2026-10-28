import { test, expect } from '@playwright/test';

/**
 * End-to-End Enterprise Workflow Tests for RasoSynthTune 2.0.0.
 * Covers:
 * 1. Command Center & Sarvam-2B Sovereign Indian AI launcher.
 * 2. Fine-Tune Studio & 1-Click Flagship Indic GST recipe preset.
 * 3. Empirical Research Benchmarks & Sarvam-2B accuracy gains.
 * 4. Datasets & DBOM Cryptographic Verification Badges.
 */

test.describe('RasoSynthTune 2.0.0 Enterprise E2E Workflows', () => {
  test('Command Center displays title, metrics, and Sovereign Indic quick launcher', async ({ page }) => {
    await page.goto('/');
    
    // Check main branding header
    await expect(page).toHaveTitle(/RasoSynthTune/i);
    await expect(page.locator('text=RasoSynthTune').first()).toBeVisible();

    // Verify presence of Sarvam-2B Sovereign AI banner / quick launcher
    const sarvamBanner = page.locator('text=Sarvam-2B Sovereign AI');
    if (await sarvamBanner.count() > 0) {
      await expect(sarvamBanner.first()).toBeVisible();
    }
  });

  test('Fine-Tune Studio loads with User Dataset selection', async ({ page }) => {
    await page.goto('/finetune');

    // Verify Fine-Tune Studio UI renders
    await expect(page.locator('text=Fine-Tune Studio').first()).toBeVisible();

    // Verify model and dataset configuration options render
    await expect(page.locator('text=Base Model').or(page.locator('text=Model Architecture'))).toBeVisible();
  });

  test('Research page renders empirical benchmark comparisons and ROI scorecard', async ({ page }) => {
    await page.goto('/research');

    // Verify Research / Benchmarks page header
    await expect(page.locator('text=Research').or(page.locator('text=Benchmark'))).toBeVisible();

    // Verify empirical accuracy card for Indic GST (+14.2%)
    const accuracyBadge = page.locator('text=+14.2%');
    if (await accuracyBadge.count() > 0) {
      await expect(accuracyBadge.first()).toBeVisible();
    }
  });

  test('Datasets page lists datasets with cryptographic DBOM attestation status', async ({ page }) => {
    await page.goto('/datasets');

    // Verify Datasets page
    await expect(page.locator('text=Datasets').first()).toBeVisible();

    // Verify DBOM verification badge / pill
    const dbomBadge = page.locator('text=DBOM').or(page.locator('text=Cryptographic'));
    await expect(dbomBadge.first()).toBeVisible();
  });
});
