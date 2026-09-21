package com.kingstreet.gilaki

import org.junit.Assert.assertEquals
import org.junit.Test

class PackageIdTest {
    @Test
    fun applicationIdIsLocked() {
        assertEquals("com.kingstreet.gilaki", BuildConfig.APPLICATION_ID)
        assertEquals("https://1404kingstreet.com/gilaki-api", BuildConfig.DEFAULT_API_BASE)
    }
}
