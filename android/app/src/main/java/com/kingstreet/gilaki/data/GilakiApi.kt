package com.kingstreet.gilaki.data

import okhttp3.MultipartBody
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path

interface GilakiApi {
    @GET("health")
    suspend fun health(): HealthResponse

    @GET("v1/presets")
    suspend fun presets(): PresetsResponse

    @GET("v1/presets/{id}")
    suspend fun preset(@Path("id") id: String): PresetDetailResponse

    @Multipart
    @POST("v1/recognize")
    suspend fun recognize(
        @Part audio: MultipartBody.Part,
        @Part mapJson: MultipartBody.Part? = null,
    ): RecognizeResponse
}
