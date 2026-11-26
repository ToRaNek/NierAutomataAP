/* Murs "zone verrouillee" dessines par le mod lui-meme (aucun modele du jeu) : un panneau translucide raye, avec
   un texte, pose dans le monde a l'entree d'une zone. Le mod s'accroche a IDXGISwapChain::Present et dessine par
   dessus l'image finie du jeu, avec la camera du jeu (position, cible et angle lus dans sa memoire aux adresses
   donnees par le client). Pas de test de profondeur : le panneau se voit a travers le decor, il s'efface avec la
   distance. */
#define WIN32_LEAN_AND_MEAN
#define COBJMACROS
#include <windows.h>
#include <d3d11.h>
#include <dxgi.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
#include "overlay.h"

#define TEX_W 1024
#define TEX_H 128
#define ROW_HEIGHT 6.0f           /* hauteur d'une rangee du motif, en metres */
#define VIEW_RANGE 90.0f          /* au-dela, le panneau est invisible : rien n'est dessine */
#define MAX_VERTS (OVERLAY_MAX_WALLS * 6)
#define NOTE_MAX 6                /* messages Archipelago affiches en meme temps */
#define NOTE_W 1024
#define NOTE_H 64
#define NOTE_FADE_MS 700

typedef struct { float x, y, z, u, v, wall; } vert_t;
typedef struct { float vp[16]; float eye[4]; float fade[4]; } cbuf_t;
typedef HRESULT(WINAPI *compile_t)(LPCVOID, SIZE_T, LPCSTR, const void *, void *, LPCSTR, LPCSTR, UINT, UINT,
                                   ID3DBlob **, ID3DBlob **);
typedef HRESULT(STDMETHODCALLTYPE *present_t)(IDXGISwapChain *, UINT, UINT);

static CRITICAL_SECTION lock;
static overlay_wall_t walls[OVERLAY_MAX_WALLS];
static int wall_count, text_dirty = 1, ready, failed;
static uint64_t cam_eye, cam_target, cam_fov;      /* adresses absolues, 0 = inconnues */
static uint64_t player_ptr;                        /* adresse du pointeur vers le joueur, 0 = pas de blocage */
static present_t real_present;
static ID3D11Device *dev;
static ID3D11DeviceContext *ctx;
static ID3D11VertexShader *vs;
static ID3D11PixelShader *ps;
static ID3D11InputLayout *layout;
static ID3D11Buffer *vbuf, *cbuf;
static ID3D11BlendState *blend;
static ID3D11RasterizerState *raster;
static ID3D11DepthStencilState *depth;
static ID3D11SamplerState *sampler;
static ID3D11Texture2D *tex;
static ID3D11ShaderResourceView *tex_view;
typedef struct { wchar_t text[128]; float rgb[3]; ULONGLONG until; int dirty; } note_t;
static note_t notes[NOTE_MAX];
static int note_count;
static ID3D11PixelShader *ps_note;
static ID3D11Texture2D *note_tex;
static ID3D11ShaderResourceView *note_view;

static const char SHADER[] =
    "cbuffer C : register(b0) { row_major float4x4 vp; float4 eye; float4 fade; };"
    "Texture2DArray t : register(t0); SamplerState s : register(s0);"
    "struct V { float4 p : SV_Position; float3 w : W; float3 uv : UV; };"
    "V vsmain(float3 pos : POSITION, float3 uv : TEXCOORD) {"
    "  V o; o.p = mul(float4(pos, 1), vp); o.w = pos; o.uv = uv; return o; }"
    "float4 psmain(V i, bool front : SV_IsFrontFace) : SV_Target {"
    "  if (front) i.uv.x = -i.uv.x;"
    "  i.uv.y = frac(i.uv.y);"                                          /* le motif se repete en hauteur */                                   /* lisible des deux cotes */
    "  float d = distance(i.w, eye.xyz);"
    "  float a = saturate((fade.x - d) / fade.y);"                    /* s'efface au loin */
    "  float stripe = step(0.5, frac((i.uv.x * 2.0 + i.uv.y) * 1.5));"
    "  float edge = step(i.uv.y, 0.06) + step(0.94, i.uv.y);"
    "  float3 col = lerp(float3(0.75, 0.08, 0.08), float3(0.95, 0.75, 0.1), stripe * 0.35);"
    "  float alpha = 0.16 + 0.5 * saturate(edge);"
    "  float band = step(0.28, i.uv.y) * step(i.uv.y, 0.72);"           /* bandeau du texte */
    "  float txt = t.Sample(s, float3(frac(i.uv.x), (i.uv.y - 0.28) / 0.44, i.uv.z)).r * band;"
    "  col = lerp(col, float3(0.05, 0.02, 0.02), band * 0.7);"
    "  alpha = max(alpha, band * 0.6);"
    "  col = lerp(col, float3(1, 1, 1), txt);"
    "  return float4(col, alpha * a); }"
    /* message a l'ecran : texte de la couleur donnee (eye.rgb), avec une ombre pour rester lisible partout */
    "float4 psnote(V i) : SV_Target {"
    "  float a = t.Sample(s, i.uv).r;"
    "  float sh = t.Sample(s, float3(i.uv.x - 0.0025, i.uv.y - 0.04, i.uv.z)).r;"
    "  return float4(eye.rgb * a, max(a, sh * 0.85) * fade.x); }";

void overlay_set(const overlay_wall_t *w, int count, uint64_t eye, uint64_t target, uint64_t fov,
                 uint64_t player) {
    if (count < 0) count = 0;
    if (count > OVERLAY_MAX_WALLS) count = OVERLAY_MAX_WALLS;
    EnterCriticalSection(&lock);
    if (count) memcpy(walls, w, sizeof(overlay_wall_t) * (size_t)count);
    wall_count = count;
    cam_eye = eye; cam_target = target; cam_fov = fov; player_ptr = player;
    text_dirty = 1;
    LeaveCriticalSection(&lock);
}

int overlay_status(void) { return failed ? -1 : ready; }

/* Ajoute un message (UTF-8) en bas a gauche de l'ecran pendant `ms` millisecondes. Le plus ancien sort s'il n'y
   a plus de place. */
void overlay_note(const char *utf8, uint32_t rgb, uint32_t ms) {
    EnterCriticalSection(&lock);
    if (note_count == NOTE_MAX) {
        memmove(&notes[0], &notes[1], sizeof(note_t) * (NOTE_MAX - 1));
        note_count--;
        for (int i = 0; i < note_count; i++) notes[i].dirty = 1;
    }
    {
        note_t *n = &notes[note_count++];
        memset(n, 0, sizeof *n);
        MultiByteToWideChar(CP_UTF8, 0, utf8, -1, n->text, 127);
        n->rgb[0] = (float)((rgb >> 16) & 255) / 255.0f;
        n->rgb[1] = (float)((rgb >> 8) & 255) / 255.0f;
        n->rgb[2] = (float)(rgb & 255) / 255.0f;
        n->until = GetTickCount64() + (ms ? ms : 6000);
        n->dirty = 1;
    }
    LeaveCriticalSection(&lock);
}

/* texte de chaque mur, dessine avec GDI dans une couche de la texture */
static void upload_text(void) {
    BITMAPINFO bi;
    void *bits = NULL;
    HDC dc = CreateCompatibleDC(NULL);
    HBITMAP bmp;
    HFONT font = NULL;
    static uint8_t gray[TEX_W * TEX_H];
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = TEX_W; bi.bmiHeader.biHeight = -TEX_H;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    bmp = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    if (!bmp || !bits) { DeleteDC(dc); return; }
    SelectObject(dc, bmp);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(255, 255, 255));
    for (int i = 0; i < wall_count; i++) {
        RECT r = {0, 0, TEX_W, TEX_H};
        SIZE sz;
        int px = 84;
        /* la taille du texte s'adapte : il doit tenir en entier dans la largeur, avec une marge */
        for (;;) {
            font = CreateFontA(px, 0, 0, 0, FW_BOLD, 0, 0, 0, ANSI_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, "Arial");
            SelectObject(dc, font);
            if (px <= 20 || !GetTextExtentPoint32A(dc, walls[i].text, lstrlenA(walls[i].text), &sz)
                || sz.cx <= TEX_W - 120) break;
            SelectObject(dc, GetStockObject(SYSTEM_FONT));
            DeleteObject(font);
            px -= 6;
        }
        memset(bits, 0, TEX_W * TEX_H * 4);
        DrawTextA(dc, walls[i].text, -1, &r, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
        GdiFlush();
        for (int p = 0; p < TEX_W * TEX_H; p++) gray[p] = ((uint8_t *)bits)[p * 4 + 1];
        ID3D11DeviceContext_UpdateSubresource(ctx, (ID3D11Resource *)tex, (UINT)i, NULL, gray, TEX_W, 0);
        SelectObject(dc, GetStockObject(SYSTEM_FONT));
        DeleteObject(font);
    }
    DeleteObject(bmp);
    DeleteDC(dc);
}

static int init(IDXGISwapChain *sc) {
    HMODULE comp = LoadLibraryA("d3dcompiler_47.dll");
    compile_t compile = comp ? (compile_t)(void *)GetProcAddress(comp, "D3DCompile") : NULL;
    ID3DBlob *vb = NULL, *pb = NULL;
    D3D11_INPUT_ELEMENT_DESC il[2] = {
        {"POSITION", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 0, D3D11_INPUT_PER_VERTEX_DATA, 0},
        {"TEXCOORD", 0, DXGI_FORMAT_R32G32B32_FLOAT, 0, 12, D3D11_INPUT_PER_VERTEX_DATA, 0}};
    D3D11_BUFFER_DESC bd;
    D3D11_BLEND_DESC bl;
    D3D11_RASTERIZER_DESC rs;
    D3D11_DEPTH_STENCIL_DESC ds;
    D3D11_SAMPLER_DESC sd;
    D3D11_TEXTURE2D_DESC td;
    if (!compile) return 0;
    if (FAILED(IDXGISwapChain_GetDevice(sc, &IID_ID3D11Device, (void **)&dev))) return 0;
    ID3D11Device_GetImmediateContext(dev, &ctx);
    if (FAILED(compile(SHADER, sizeof SHADER - 1, NULL, NULL, NULL, "vsmain", "vs_4_0", 0, 0, &vb, NULL))) return 0;
    if (FAILED(compile(SHADER, sizeof SHADER - 1, NULL, NULL, NULL, "psmain", "ps_4_0", 0, 0, &pb, NULL))) return 0;
    if (FAILED(ID3D11Device_CreateVertexShader(dev, ID3D10Blob_GetBufferPointer(vb), ID3D10Blob_GetBufferSize(vb),
                                               NULL, &vs))) return 0;
    if (FAILED(ID3D11Device_CreatePixelShader(dev, ID3D10Blob_GetBufferPointer(pb), ID3D10Blob_GetBufferSize(pb),
                                              NULL, &ps))) return 0;
    if (FAILED(ID3D11Device_CreateInputLayout(dev, il, 2, ID3D10Blob_GetBufferPointer(vb),
                                              ID3D10Blob_GetBufferSize(vb), &layout))) return 0;
    memset(&bd, 0, sizeof bd);
    bd.ByteWidth = sizeof(vert_t) * MAX_VERTS; bd.Usage = D3D11_USAGE_DYNAMIC;
    bd.BindFlags = D3D11_BIND_VERTEX_BUFFER; bd.CPUAccessFlags = D3D11_CPU_ACCESS_WRITE;
    if (FAILED(ID3D11Device_CreateBuffer(dev, &bd, NULL, &vbuf))) return 0;
    bd.ByteWidth = sizeof(cbuf_t); bd.BindFlags = D3D11_BIND_CONSTANT_BUFFER;
    if (FAILED(ID3D11Device_CreateBuffer(dev, &bd, NULL, &cbuf))) return 0;
    memset(&bl, 0, sizeof bl);
    bl.RenderTarget[0].BlendEnable = TRUE;
    bl.RenderTarget[0].SrcBlend = D3D11_BLEND_SRC_ALPHA; bl.RenderTarget[0].DestBlend = D3D11_BLEND_INV_SRC_ALPHA;
    bl.RenderTarget[0].BlendOp = D3D11_BLEND_OP_ADD;
    bl.RenderTarget[0].SrcBlendAlpha = D3D11_BLEND_ONE; bl.RenderTarget[0].DestBlendAlpha = D3D11_BLEND_ONE;
    bl.RenderTarget[0].BlendOpAlpha = D3D11_BLEND_OP_ADD;
    bl.RenderTarget[0].RenderTargetWriteMask = D3D11_COLOR_WRITE_ENABLE_ALL;
    if (FAILED(ID3D11Device_CreateBlendState(dev, &bl, &blend))) return 0;
    memset(&rs, 0, sizeof rs);
    rs.FillMode = D3D11_FILL_SOLID; rs.CullMode = D3D11_CULL_NONE; rs.DepthClipEnable = TRUE;
    if (FAILED(ID3D11Device_CreateRasterizerState(dev, &rs, &raster))) return 0;
    memset(&ds, 0, sizeof ds);
    if (FAILED(ID3D11Device_CreateDepthStencilState(dev, &ds, &depth))) return 0;
    memset(&sd, 0, sizeof sd);
    sd.Filter = D3D11_FILTER_MIN_MAG_MIP_LINEAR;
    sd.AddressU = D3D11_TEXTURE_ADDRESS_WRAP; sd.AddressV = D3D11_TEXTURE_ADDRESS_CLAMP;
    sd.AddressW = D3D11_TEXTURE_ADDRESS_CLAMP; sd.MaxLOD = D3D11_FLOAT32_MAX;
    if (FAILED(ID3D11Device_CreateSamplerState(dev, &sd, &sampler))) return 0;
    memset(&td, 0, sizeof td);
    td.Width = TEX_W; td.Height = TEX_H; td.MipLevels = 1; td.ArraySize = OVERLAY_MAX_WALLS;
    td.Format = DXGI_FORMAT_R8_UNORM; td.SampleDesc.Count = 1; td.BindFlags = D3D11_BIND_SHADER_RESOURCE;
    if (FAILED(ID3D11Device_CreateTexture2D(dev, &td, NULL, &tex))) return 0;
    if (FAILED(ID3D11Device_CreateShaderResourceView(dev, (ID3D11Resource *)tex, NULL, &tex_view))) return 0;
    {
        ID3DBlob *nb = NULL;
        if (FAILED(compile(SHADER, sizeof SHADER - 1, NULL, NULL, NULL, "psnote", "ps_4_0", 0, 0, &nb, NULL))) return 0;
        if (FAILED(ID3D11Device_CreatePixelShader(dev, ID3D10Blob_GetBufferPointer(nb), ID3D10Blob_GetBufferSize(nb),
                                                  NULL, &ps_note))) return 0;
        td.Width = NOTE_W; td.Height = NOTE_H; td.ArraySize = NOTE_MAX;
        if (FAILED(ID3D11Device_CreateTexture2D(dev, &td, NULL, &note_tex))) return 0;
        if (FAILED(ID3D11Device_CreateShaderResourceView(dev, (ID3D11Resource *)note_tex, NULL, &note_view))) return 0;
    }
    return 1;
}

static int read_floats(uint64_t addr, float *out, int n) {
    SIZE_T got = 0;
    return addr && ReadProcessMemory(GetCurrentProcess(), (void *)addr, out, sizeof(float) * (size_t)n, &got)
        && got == sizeof(float) * (size_t)n;
}

/* vue (regard vers la cible, Y en haut) x projection, vecteurs ligne */
static void view_proj(const float *e, const float *t, float fov, float aspect, float *m) {
    float f[3] = {t[0] - e[0], t[1] - e[1], t[2] - e[2]}, r[3], u[3], n, h, w, zn = 0.1f, zf = 2000.0f;
    n = sqrtf(f[0] * f[0] + f[1] * f[1] + f[2] * f[2]); if (n < 1e-4f) n = 1;
    f[0] /= n; f[1] /= n; f[2] /= n;
    r[0] = -f[2]; r[1] = 0; r[2] = f[0];                 /* droite de l'ecran (verifie en jeu avec le stick) */
    n = sqrtf(r[0] * r[0] + r[2] * r[2]); if (n < 1e-4f) n = 1;
    r[0] /= n; r[2] /= n;
    u[0] = r[1] * f[2] - r[2] * f[1]; u[1] = r[2] * f[0] - r[0] * f[2]; u[2] = r[0] * f[1] - r[1] * f[0];
    h = 1.0f / tanf(fov * 0.5f); w = h / aspect;
    {
        float tx = -(r[0] * e[0] + r[1] * e[1] + r[2] * e[2]), ty = -(u[0] * e[0] + u[1] * e[1] + u[2] * e[2]);
        float tz = -(f[0] * e[0] + f[1] * e[1] + f[2] * e[2]), q = zf / (zf - zn);
        /* colonnes : x' = r, y' = u, z' = f ; puis projection (w, h, q, 1) */
        m[0] = r[0] * w; m[1] = u[0] * h; m[2] = f[0] * q; m[3] = f[0];
        m[4] = r[1] * w; m[5] = u[1] * h; m[6] = f[1] * q; m[7] = f[1];
        m[8] = r[2] * w; m[9] = u[2] * h; m[10] = f[2] * q; m[11] = f[2];
        m[12] = tx * w; m[13] = ty * h; m[14] = tz * q - zn * q; m[15] = tz;
    }
}

/* Etat graphique du jeu que le dessin des panneaux modifie : sauvegarde avant, remis apres. Le moteur du jeu ne
   repose pas forcement tout a chaque image ; sans ca, ce qu'on laisse derriere nous peut fausser son rendu. */
typedef struct {
    ID3D11RenderTargetView *rtv[D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT];
    ID3D11DepthStencilView *dsv;
    D3D11_VIEWPORT vp[D3D11_VIEWPORT_AND_SCISSORRECT_OBJECT_COUNT_PER_PIPELINE];
    UINT nvp;
    ID3D11RasterizerState *rs;
    ID3D11BlendState *bs; FLOAT bf[4]; UINT mask;
    ID3D11DepthStencilState *dss; UINT sref;
    ID3D11InputLayout *il; D3D11_PRIMITIVE_TOPOLOGY topo;
    ID3D11Buffer *vb; UINT stride, offset;
    ID3D11VertexShader *vs; ID3D11PixelShader *ps; ID3D11GeometryShader *gs; ID3D11HullShader *hs;
    ID3D11DomainShader *ds;
    ID3D11ClassInstance *vsi[256], *psi[256], *gsi[256], *hsi[256], *dsi[256];
    UINT nvsi, npsi, ngsi, nhsi, ndsi;
    ID3D11Buffer *vscb, *pscb;
    ID3D11ShaderResourceView *srv;
    ID3D11SamplerState *smp;
} saved_t;

#define REL(x) do { if (x) IUnknown_Release((IUnknown *)(x)); } while (0)

static void state_save(saved_t *b) {
    memset(b, 0, sizeof *b);
    ID3D11DeviceContext_OMGetRenderTargets(ctx, D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, b->rtv, &b->dsv);
    b->nvp = D3D11_VIEWPORT_AND_SCISSORRECT_OBJECT_COUNT_PER_PIPELINE;
    ID3D11DeviceContext_RSGetViewports(ctx, &b->nvp, b->vp);
    ID3D11DeviceContext_RSGetState(ctx, &b->rs);
    ID3D11DeviceContext_OMGetBlendState(ctx, &b->bs, b->bf, &b->mask);
    ID3D11DeviceContext_OMGetDepthStencilState(ctx, &b->dss, &b->sref);
    ID3D11DeviceContext_IAGetInputLayout(ctx, &b->il);
    ID3D11DeviceContext_IAGetPrimitiveTopology(ctx, &b->topo);
    ID3D11DeviceContext_IAGetVertexBuffers(ctx, 0, 1, &b->vb, &b->stride, &b->offset);
    b->nvsi = b->npsi = b->ngsi = b->nhsi = b->ndsi = 256;
    ID3D11DeviceContext_VSGetShader(ctx, &b->vs, b->vsi, &b->nvsi);
    ID3D11DeviceContext_PSGetShader(ctx, &b->ps, b->psi, &b->npsi);
    ID3D11DeviceContext_GSGetShader(ctx, &b->gs, b->gsi, &b->ngsi);
    ID3D11DeviceContext_HSGetShader(ctx, &b->hs, b->hsi, &b->nhsi);
    ID3D11DeviceContext_DSGetShader(ctx, &b->ds, b->dsi, &b->ndsi);
    ID3D11DeviceContext_VSGetConstantBuffers(ctx, 0, 1, &b->vscb);
    ID3D11DeviceContext_PSGetConstantBuffers(ctx, 0, 1, &b->pscb);
    ID3D11DeviceContext_PSGetShaderResources(ctx, 0, 1, &b->srv);
    ID3D11DeviceContext_PSGetSamplers(ctx, 0, 1, &b->smp);
}

static void state_restore(saved_t *b) {
    UINT i;
    ID3D11DeviceContext_OMSetRenderTargets(ctx, D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT, b->rtv, b->dsv);
    ID3D11DeviceContext_RSSetViewports(ctx, b->nvp, b->vp);
    ID3D11DeviceContext_RSSetState(ctx, b->rs);
    ID3D11DeviceContext_OMSetBlendState(ctx, b->bs, b->bf, b->mask);
    ID3D11DeviceContext_OMSetDepthStencilState(ctx, b->dss, b->sref);
    ID3D11DeviceContext_IASetInputLayout(ctx, b->il);
    ID3D11DeviceContext_IASetPrimitiveTopology(ctx, b->topo);
    ID3D11DeviceContext_IASetVertexBuffers(ctx, 0, 1, &b->vb, &b->stride, &b->offset);
    ID3D11DeviceContext_VSSetShader(ctx, b->vs, b->vsi, b->nvsi);
    ID3D11DeviceContext_PSSetShader(ctx, b->ps, b->psi, b->npsi);
    ID3D11DeviceContext_GSSetShader(ctx, b->gs, b->gsi, b->ngsi);
    ID3D11DeviceContext_HSSetShader(ctx, b->hs, b->hsi, b->nhsi);
    ID3D11DeviceContext_DSSetShader(ctx, b->ds, b->dsi, b->ndsi);
    ID3D11DeviceContext_VSSetConstantBuffers(ctx, 0, 1, &b->vscb);
    ID3D11DeviceContext_PSSetConstantBuffers(ctx, 0, 1, &b->pscb);
    ID3D11DeviceContext_PSSetShaderResources(ctx, 0, 1, &b->srv);
    ID3D11DeviceContext_PSSetSamplers(ctx, 0, 1, &b->smp);
    for (i = 0; i < D3D11_SIMULTANEOUS_RENDER_TARGET_COUNT; i++) REL(b->rtv[i]);
    REL(b->dsv); REL(b->rs); REL(b->bs); REL(b->dss); REL(b->il); REL(b->vb);
    REL(b->vs); REL(b->ps); REL(b->gs); REL(b->hs); REL(b->ds);
    for (i = 0; i < b->nvsi; i++) REL(b->vsi[i]);
    for (i = 0; i < b->npsi; i++) REL(b->psi[i]);
    for (i = 0; i < b->ngsi; i++) REL(b->gsi[i]);
    for (i = 0; i < b->nhsi; i++) REL(b->hsi[i]);
    for (i = 0; i < b->ndsi; i++) REL(b->dsi[i]);
    REL(b->vscb); REL(b->pscb); REL(b->srv); REL(b->smp);
}

static saved_t saved;

static void draw(IDXGISwapChain *sc) {
    ID3D11Texture2D *back = NULL;
    ID3D11RenderTargetView *rtv = NULL;
    D3D11_TEXTURE2D_DESC bd;
    D3D11_MAPPED_SUBRESOURCE map;
    D3D11_VIEWPORT vp;
    cbuf_t cb;
    float eye[3], target[3], fov = 0.873f, bf[4] = {0, 0, 0, 0};
    UINT stride = sizeof(vert_t), offset = 0;
    int n;
    EnterCriticalSection(&lock);
    n = wall_count;
    if (!n || !read_floats(cam_eye, eye, 3) || !read_floats(cam_target, target, 3)) { LeaveCriticalSection(&lock); return; }
    {   /* Aucun panneau a portee de vue (ils s'effacent a 60 m) : on ne touche a RIEN du rendu du jeu. */
        int near_one = 0;
        for (int i = 0; i < n && !near_one; i++) {
            float cx = (walls[i].x1 + walls[i].x2) * 0.5f - eye[0], cz = (walls[i].z1 + walls[i].z2) * 0.5f - eye[2];
            float half = 0.5f * sqrtf((walls[i].x2 - walls[i].x1) * (walls[i].x2 - walls[i].x1)
                                      + (walls[i].z2 - walls[i].z1) * (walls[i].z2 - walls[i].z1));
            if (sqrtf(cx * cx + cz * cz) < VIEW_RANGE + half) near_one = 1;
        }
        if (!near_one) { LeaveCriticalSection(&lock); return; }
    }
    read_floats(cam_fov, &fov, 1);
    if (!(fov > 0.2f && fov < 2.5f)) fov = 0.873f;
    if (text_dirty) { upload_text(); text_dirty = 0; }
    if (FAILED(ID3D11DeviceContext_Map(ctx, (ID3D11Resource *)vbuf, 0, D3D11_MAP_WRITE_DISCARD, 0, &map))) {
        LeaveCriticalSection(&lock); return;
    }
    for (int i = 0; i < n; i++) {
        const overlay_wall_t *w = &walls[i];
        vert_t *v = (vert_t *)map.pData + i * 6;
        float len = sqrtf((w->x2 - w->x1) * (w->x2 - w->x1) + (w->z2 - w->z1) * (w->z2 - w->z1));
        float rows = floorf(w->height / ROW_HEIGHT + 0.5f), rep;
        if (rows < 1) rows = 1;
        rep = floorf(len / (ROW_HEIGHT * (float)TEX_W / (float)TEX_H * 0.44f) + 0.5f);   /* texte non deforme */
        if (rep < 1) rep = 1;
        vert_t q[4] = {{w->x1, w->y, w->z1, 0, rows, (float)i}, {w->x2, w->y, w->z2, rep, rows, (float)i},
                       {w->x2, w->y + w->height, w->z2, rep, 0, (float)i},
                       {w->x1, w->y + w->height, w->z1, 0, 0, (float)i}};
        v[0] = q[0]; v[1] = q[1]; v[2] = q[2]; v[3] = q[0]; v[4] = q[2]; v[5] = q[3];
    }
    ID3D11DeviceContext_Unmap(ctx, (ID3D11Resource *)vbuf, 0);
    LeaveCriticalSection(&lock);
    if (FAILED(IDXGISwapChain_GetBuffer(sc, 0, &IID_ID3D11Texture2D, (void **)&back))) return;
    ID3D11Texture2D_GetDesc(back, &bd);
    if (FAILED(ID3D11Device_CreateRenderTargetView(dev, (ID3D11Resource *)back, NULL, &rtv))) {
        ID3D11Texture2D_Release(back); return;
    }
    view_proj(eye, target, fov, (float)bd.Width / (float)bd.Height, cb.vp);
    cb.eye[0] = eye[0]; cb.eye[1] = eye[1]; cb.eye[2] = eye[2]; cb.eye[3] = 0;
    cb.fade[0] = 60.0f; cb.fade[1] = 25.0f; cb.fade[2] = cb.fade[3] = 0;
    if (SUCCEEDED(ID3D11DeviceContext_Map(ctx, (ID3D11Resource *)cbuf, 0, D3D11_MAP_WRITE_DISCARD, 0, &map))) {
        memcpy(map.pData, &cb, sizeof cb);
        ID3D11DeviceContext_Unmap(ctx, (ID3D11Resource *)cbuf, 0);
    }
    vp.TopLeftX = vp.TopLeftY = 0; vp.Width = (float)bd.Width; vp.Height = (float)bd.Height;
    vp.MinDepth = 0; vp.MaxDepth = 1;
    state_save(&saved);
    ID3D11DeviceContext_OMSetRenderTargets(ctx, 1, &rtv, NULL);
    ID3D11DeviceContext_RSSetViewports(ctx, 1, &vp);
    ID3D11DeviceContext_RSSetState(ctx, raster);
    ID3D11DeviceContext_OMSetBlendState(ctx, blend, bf, 0xFFFFFFFF);
    ID3D11DeviceContext_OMSetDepthStencilState(ctx, depth, 0);
    ID3D11DeviceContext_IASetInputLayout(ctx, layout);
    ID3D11DeviceContext_IASetPrimitiveTopology(ctx, D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ID3D11DeviceContext_IASetVertexBuffers(ctx, 0, 1, &vbuf, &stride, &offset);
    ID3D11DeviceContext_VSSetShader(ctx, vs, NULL, 0);
    ID3D11DeviceContext_VSSetConstantBuffers(ctx, 0, 1, &cbuf);
    ID3D11DeviceContext_PSSetShader(ctx, ps, NULL, 0);
    ID3D11DeviceContext_PSSetConstantBuffers(ctx, 0, 1, &cbuf);
    ID3D11DeviceContext_PSSetShaderResources(ctx, 0, 1, &tex_view);
    ID3D11DeviceContext_PSSetSamplers(ctx, 0, 1, &sampler);
    ID3D11DeviceContext_GSSetShader(ctx, NULL, NULL, 0);
    ID3D11DeviceContext_HSSetShader(ctx, NULL, NULL, 0);
    ID3D11DeviceContext_DSSetShader(ctx, NULL, NULL, 0);
    ID3D11DeviceContext_Draw(ctx, (UINT)n * 6, 0);
    state_restore(&saved);
    ID3D11RenderTargetView_Release(rtv);
    ID3D11Texture2D_Release(back);
}

/* Le panneau arrete le joueur : a chaque image, s'il a franchi la ligne du panneau (dans sa largeur et sa
   hauteur), il est remis juste devant, cote ville. Le cote "zone" est a droite du segment (x1,z1)->(x2,z2).
   Au-dela de DEPTH metres derriere la ligne on ne touche a rien (joueur deja dans la zone apres un chargement). */
#define BLOCK_MARGIN 0.8f
#define BLOCK_DEPTH 6.0f
static void block_player(void) {
    HANDLE self = GetCurrentProcess();
    uint64_t pl = 0;
    float p[3];
    SIZE_T n = 0;
    EnterCriticalSection(&lock);
    if (!player_ptr || !wall_count
        || !ReadProcessMemory(self, (void *)player_ptr, &pl, sizeof pl, &n) || n != sizeof pl || !pl
        || !ReadProcessMemory(self, (void *)(pl + 0x50), p, sizeof p, &n) || n != sizeof p) {
        LeaveCriticalSection(&lock);
        return;
    }
    for (int i = 0; i < wall_count; i++) {
        const overlay_wall_t *w = &walls[i];
        float tx = w->x2 - w->x1, tz = w->z2 - w->z1, len = sqrtf(tx * tx + tz * tz), nx, nz, rx, rz, along, d;
        if (len < 0.5f) continue;
        tx /= len; tz /= len; nx = tz; nz = -tx;
        rx = p[0] - (w->x1 + w->x2) * 0.5f; rz = p[2] - (w->z1 + w->z2) * 0.5f;
        along = rx * tx + rz * tz; d = rx * nx + rz * nz;
        if (fabsf(along) > len * 0.5f || p[1] < w->y - 4.0f || p[1] > w->y + w->height + 12.0f) continue;
        if (d > -BLOCK_MARGIN && d < BLOCK_DEPTH) {
            float back = d + BLOCK_MARGIN, out[3] = {p[0] - nx * back, p[1], p[2] - nz * back};
            WriteProcessMemory(self, (void *)(pl + 0x50), out, sizeof out, &n);
            break;
        }
    }
    LeaveCriticalSection(&lock);
}

/* texte d'un message, dessine avec GDI dans sa couche de texture (aligne a gauche) */
static void upload_note(int i) {
    static uint8_t gray[NOTE_W * NOTE_H];
    BITMAPINFO bi;
    void *bits = NULL;
    HDC dc = CreateCompatibleDC(NULL);
    HBITMAP bmp;
    HFONT font;
    RECT r = {8, 0, NOTE_W, NOTE_H};
    memset(&bi, 0, sizeof bi);
    bi.bmiHeader.biSize = sizeof bi.bmiHeader;
    bi.bmiHeader.biWidth = NOTE_W; bi.bmiHeader.biHeight = -NOTE_H;
    bi.bmiHeader.biPlanes = 1; bi.bmiHeader.biBitCount = 32;
    bmp = CreateDIBSection(dc, &bi, DIB_RGB_COLORS, &bits, NULL, 0);
    if (!bmp || !bits) { DeleteDC(dc); return; }
    SelectObject(dc, bmp);
    font = CreateFontA(44, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, 0, "Arial");
    SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, RGB(255, 255, 255));
    memset(bits, 0, NOTE_W * NOTE_H * 4);
    DrawTextW(dc, notes[i].text, -1, &r, DT_LEFT | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX | DT_END_ELLIPSIS);
    GdiFlush();
    for (int p = 0; p < NOTE_W * NOTE_H; p++) gray[p] = ((uint8_t *)bits)[p * 4 + 1];
    ID3D11DeviceContext_UpdateSubresource(ctx, (ID3D11Resource *)note_tex, (UINT)i, NULL, gray, NOTE_W, 0);
    SelectObject(dc, GetStockObject(SYSTEM_FONT));
    DeleteObject(font);
    DeleteObject(bmp);
    DeleteDC(dc);
}

/* messages Archipelago : lignes de texte colore en bas a gauche, par-dessus l'image finie */
static void draw_notes(IDXGISwapChain *sc) {
    ID3D11Texture2D *back = NULL;
    ID3D11RenderTargetView *rtv = NULL;
    D3D11_TEXTURE2D_DESC bd;
    D3D11_MAPPED_SUBRESOURCE map;
    D3D11_VIEWPORT vp;
    float bf[4] = {0, 0, 0, 0}, rgb[NOTE_MAX][3], alpha[NOTE_MAX], lh = 0.075f, lw, x0 = -0.96f, bottom = -0.80f;
    UINT stride = sizeof(vert_t), offset = 0;
    ULONGLONG now = GetTickCount64();
    int n, keep = 0;
    EnterCriticalSection(&lock);
    for (int i = 0; i < note_count; i++) {             /* retire les messages finis */
        if (notes[i].until > now) {
            if (keep != i) { notes[keep] = notes[i]; notes[keep].dirty = 1; }
            keep++;
        }
    }
    note_count = n = keep;
    if (!n) { LeaveCriticalSection(&lock); return; }
    for (int i = 0; i < n; i++) {
        ULONGLONG left = notes[i].until - now;
        if (notes[i].dirty) { upload_note(i); notes[i].dirty = 0; }
        memcpy(rgb[i], notes[i].rgb, sizeof rgb[i]);
        alpha[i] = left >= NOTE_FADE_MS ? 1.0f : (float)left / (float)NOTE_FADE_MS;
    }
    LeaveCriticalSection(&lock);
    if (FAILED(IDXGISwapChain_GetBuffer(sc, 0, &IID_ID3D11Texture2D, (void **)&back))) return;
    ID3D11Texture2D_GetDesc(back, &bd);
    if (FAILED(ID3D11Device_CreateRenderTargetView(dev, (ID3D11Resource *)back, NULL, &rtv))) {
        ID3D11Texture2D_Release(back); return;
    }
    lw = lh * ((float)NOTE_W / (float)NOTE_H) * ((float)bd.Height / (float)bd.Width);     /* texte non deforme */
    if (FAILED(ID3D11DeviceContext_Map(ctx, (ID3D11Resource *)vbuf, 0, D3D11_MAP_WRITE_DISCARD, 0, &map))) {
        ID3D11RenderTargetView_Release(rtv); ID3D11Texture2D_Release(back); return;
    }
    for (int i = 0; i < n; i++) {
        vert_t *v = (vert_t *)map.pData + i * 6;
        float y0 = bottom + lh * (float)(n - 1 - i), y1 = y0 + lh, x1 = x0 + lw;   /* le plus recent en bas */
        vert_t q[4] = {{x0, y0, 0.5f, 0, 1, (float)i}, {x1, y0, 0.5f, 1, 1, (float)i},
                       {x1, y1, 0.5f, 1, 0, (float)i}, {x0, y1, 0.5f, 0, 0, (float)i}};
        v[0] = q[0]; v[1] = q[1]; v[2] = q[2]; v[3] = q[0]; v[4] = q[2]; v[5] = q[3];
    }
    ID3D11DeviceContext_Unmap(ctx, (ID3D11Resource *)vbuf, 0);
    vp.TopLeftX = vp.TopLeftY = 0; vp.Width = (float)bd.Width; vp.Height = (float)bd.Height;
    vp.MinDepth = 0; vp.MaxDepth = 1;
    state_save(&saved);
    ID3D11DeviceContext_OMSetRenderTargets(ctx, 1, &rtv, NULL);
    ID3D11DeviceContext_RSSetViewports(ctx, 1, &vp);
    ID3D11DeviceContext_RSSetState(ctx, raster);
    ID3D11DeviceContext_OMSetBlendState(ctx, blend, bf, 0xFFFFFFFF);
    ID3D11DeviceContext_OMSetDepthStencilState(ctx, depth, 0);
    ID3D11DeviceContext_IASetInputLayout(ctx, layout);
    ID3D11DeviceContext_IASetPrimitiveTopology(ctx, D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST);
    ID3D11DeviceContext_IASetVertexBuffers(ctx, 0, 1, &vbuf, &stride, &offset);
    ID3D11DeviceContext_VSSetShader(ctx, vs, NULL, 0);
    ID3D11DeviceContext_VSSetConstantBuffers(ctx, 0, 1, &cbuf);
    ID3D11DeviceContext_PSSetShader(ctx, ps_note, NULL, 0);
    ID3D11DeviceContext_PSSetConstantBuffers(ctx, 0, 1, &cbuf);
    ID3D11DeviceContext_PSSetShaderResources(ctx, 0, 1, &note_view);
    ID3D11DeviceContext_PSSetSamplers(ctx, 0, 1, &sampler);
    ID3D11DeviceContext_GSSetShader(ctx, NULL, NULL, 0);
    ID3D11DeviceContext_HSSetShader(ctx, NULL, NULL, 0);
    ID3D11DeviceContext_DSSetShader(ctx, NULL, NULL, 0);
    for (int i = 0; i < n; i++) {
        cbuf_t cb;
        memset(&cb, 0, sizeof cb);
        cb.vp[0] = cb.vp[5] = cb.vp[10] = cb.vp[15] = 1.0f;          /* positions deja a l'ecran */
        cb.eye[0] = rgb[i][0]; cb.eye[1] = rgb[i][1]; cb.eye[2] = rgb[i][2];
        cb.fade[0] = alpha[i];
        if (SUCCEEDED(ID3D11DeviceContext_Map(ctx, (ID3D11Resource *)cbuf, 0, D3D11_MAP_WRITE_DISCARD, 0, &map))) {
            memcpy(map.pData, &cb, sizeof cb);
            ID3D11DeviceContext_Unmap(ctx, (ID3D11Resource *)cbuf, 0);
            ID3D11DeviceContext_Draw(ctx, 6, (UINT)i * 6);
        }
    }
    state_restore(&saved);
    ID3D11RenderTargetView_Release(rtv);
    ID3D11Texture2D_Release(back);
}

static HRESULT STDMETHODCALLTYPE hook_present(IDXGISwapChain *sc, UINT sync, UINT flags) {
    if (wall_count) block_player();
    if (!failed && (wall_count || note_count)) {
        if (!ready) { if (init(sc)) ready = 1; else failed = 1; }
        if (ready && wall_count) draw(sc);
        if (ready && note_count) draw_notes(sc);
    }
    return real_present(sc, sync, flags);
}

/* La table de fonctions de la chaine d'images est commune a toutes les chaines : on en cree une bidon pour la
   trouver, et on y remplace Present. */
static DWORD WINAPI install_thread(LPVOID unused) {
    DXGI_SWAP_CHAIN_DESC d;
    IDXGISwapChain *sc = NULL;
    ID3D11Device *d3 = NULL;
    ID3D11DeviceContext *c3 = NULL;
    D3D_FEATURE_LEVEL lvl;
    WNDCLASSA wc;
    HWND w;
    void **vt;
    DWORD old;
    (void)unused;
    Sleep(8000);                                        /* laisser le jeu creer sa fenetre et son rendu */
    memset(&wc, 0, sizeof wc);
    wc.lpfnWndProc = DefWindowProcA; wc.hInstance = GetModuleHandleA(NULL); wc.lpszClassName = "NierApModDummy";
    RegisterClassA(&wc);
    w = CreateWindowA("NierApModDummy", "", WS_OVERLAPPED, 0, 0, 16, 16, NULL, NULL, wc.hInstance, NULL);
    if (!w) { failed = 1; return 0; }
    memset(&d, 0, sizeof d);
    d.BufferCount = 1; d.BufferDesc.Width = 16; d.BufferDesc.Height = 16;
    d.BufferDesc.Format = DXGI_FORMAT_R8G8B8A8_UNORM; d.BufferUsage = DXGI_USAGE_RENDER_TARGET_OUTPUT;
    d.OutputWindow = w; d.SampleDesc.Count = 1; d.Windowed = TRUE;
    if (FAILED(D3D11CreateDeviceAndSwapChain(NULL, D3D_DRIVER_TYPE_HARDWARE, NULL, 0, NULL, 0, D3D11_SDK_VERSION,
                                             &d, &sc, &d3, &lvl, &c3))) {
        DestroyWindow(w); failed = 1; return 0;
    }
    vt = *(void ***)sc;
    real_present = (present_t)vt[8];
    if (VirtualProtect(&vt[8], sizeof(void *), PAGE_READWRITE, &old)) {
        vt[8] = (void *)hook_present;
        VirtualProtect(&vt[8], sizeof(void *), old, &old);
    } else {
        failed = 1;
    }
    IDXGISwapChain_Release(sc);
    ID3D11DeviceContext_Release(c3);
    ID3D11Device_Release(d3);
    DestroyWindow(w);
    return 0;
}

void overlay_start(void) {
    HANDLE t;
    InitializeCriticalSection(&lock);
    t = CreateThread(NULL, 0, install_thread, NULL, 0, NULL);
    if (t) CloseHandle(t);
}
