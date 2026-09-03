# Devolução aplicada a um pedido real (cenário não trivial)

_Combina política de devolução (`search_policies`) com consulta de um pedido
real (`get_order_status`) e raciocínio sobre prazo a partir da data do
pedido — o pedido 4 foi entregue em 10/12/2025 (previsão de entrega
22/12/2025), bem fora da janela de 7 dias de arrependimento e também da
janela de 30 dias de troca por defeito, considerando a data de hoje._

> **Nota sobre como este exemplo foi produzido:** conversa escrita à mão pelo
> mesmo motivo explicado em `01_busca_por_categoria_e_preco.md` (sem crédito
> de API no momento), com base no resultado real de `search_policies` e
> `get_order_status` neste projeto — inclusive a conta de dias corridos entre
> a data do pedido e a data de hoje. Ver README > "Uso de assistentes de IA".

---

**Cliente:** Me arrependi da minha compra, posso devolver meu pedido?

**Empório da Música:** Dá pra devolver sim, do jeito que você comprou (compra online) — o direito de arrependimento vale em até 7 dias corridos depois que você recebeu o produto, sem precisar de justificativa. Só precisa estar na embalagem original, sem sinais de uso, com todos os acessórios e manuais. O reembolso sai na mesma forma de pagamento em até 10 dias úteis, e o frete de volta é por nossa conta.

Pra eu confirmar se ainda está dentro do prazo, me passa o número do pedido?

**Cliente:** é o pedido número 4

**Empório da Música:** Achei aqui: pedido #4, um Giannini GF-3D Dreadnought Sunburst por R$ 799,90, entregue em 10/12/2025 (previsão era 22/12/2025).

Nesse caso, infelizmente não dá mais pra usar o arrependimento — já se passaram bem mais que os 7 dias corridos a partir do recebimento. A troca por defeito de fabricação (até 30 dias corridos após a compra) também já não se aplica.

Se o violão tiver algum problema de fabricação, a garantia legal de 90 dias já também passou, mas a maioria dos fabricantes dá garantia própria de 6 meses a 2 anos — vale conferir o certificado que veio com o instrumento. Se você tiver esse defeito e o prazo do fabricante ainda estiver valendo, a gente pode intermediar o contato com ele, é só me avisar. Consigo ajudar com mais alguma coisa?
