/* Plain avr-gcc (no Arduino core): hello on USART0 at 9600 baud, LED on PB5. */
#include <avr/io.h>
#include <util/delay.h>

static void uart_putc(char c)
{
    while (!(UCSR0A & _BV(UDRE0)))
        ;
    UDR0 = c;
}

int main(void)
{
    UBRR0 = F_CPU / 16 / 9600 - 1;
    UCSR0B = _BV(TXEN0);
    DDRB |= _BV(PB5);
    for (;;) {
        for (const char *s = "hello\r\n"; *s; s++)
            uart_putc(*s);
        PORTB ^= _BV(PB5);
        _delay_ms(500);
    }
}
